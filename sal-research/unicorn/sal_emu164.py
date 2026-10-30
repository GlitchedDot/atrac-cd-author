#!/usr/bin/env python3
"""Unicorn HLE harness for salwrap.dll + OMGUtils.dll (ATRAC SAL dynamic stage).

Loads the two Sony DLLs as real code at their preferred bases, satisfies every
system-DLL import with a Python implementation behind a stub page, then runs
DllMain x2 and calls the manager bootstrap FUN_6511D680. An allocation ledger
records every guest-visible allocation for later memory mining.
"""
import os, sys, struct, fnmatch
import pefile
from unicorn import *
from unicorn.x86_const import *

SONY_DIR = '/home/hatch/workspace/atrac-cd-stage0/batch2/Sony Shared/OpenMG'
REPO_WIN = 'C:\\Program Files (x86)\\Common Files\\Sony Shared\\OpenMG'
CONTENT_WIN = 'C:\\ProgramData\\SonicStage\\Contents\\'
# run152 FIX: guest Repository paths land on a byte-identical MIRROR of
# the corpus OpenMG folder (MD5-verified before the run), so guest
# reads/writes behave as on the real install without ever modifying
# corpus evidence. (Through run 147 HOST_FS pointed REPO at SONY_DIR
# but host_path()'s join discarded it — see the run152 host_path fix —
# so no guest access ever actually reached either location.)
REPO_HOST = '/home/hatch/workspace/atrac-salwrap-work/unicorn/scratch/repo-mirror'
HOST_FS = {  # windows path prefix (lower) -> host dir for file IO
    REPO_WIN.lower(): REPO_HOST,
    CONTENT_WIN.lower(): '/home/hatch/workspace/atrac-salwrap-work/unicorn/scratch/contents',
    'c:\\': '/home/hatch/workspace/atrac-salwrap-work/unicorn/scratch/root',
}
os.makedirs(HOST_FS[CONTENT_WIN.lower()], exist_ok=True)
os.makedirs(HOST_FS['c:\\'], exist_ok=True)

# ---- guest memory map ----
STUB_BASE   = 0x20000000
STUB_SIZE   = 0x00010000
HALT_IDX    = 0
HEAP_BASE   = 0x10000000
HEAP_SIZE   = 0x08000000          # 128 MiB
VA_BASE     = 0x30000000          # VirtualAlloc arena
VA_SIZE     = 0x10000000
STACK_BASE  = 0x0E000000
STACK_SIZE  = 0x01400000
TEB_BASE    = 0x00000000          # FS base is stuck at 0 in this Unicorn build
PEB_BASE    = 0x00002000          # (segment loads are refused), so the TEB
AUX_BASE    = 0x00003000          # lives at linear 0; fs:[x] == linear [x].
EXE_BASE    = 0x00400000
OMG_BASE    = 0x63900000
SAL_BASE    = 0x65100000

TRACE = []

# ---- run152: VM-service-callback census state (module-global) ----
_CB17 = {'win': 'boot', 'counts': {}, 'detail': [], 'hdepth': 0}
_CB17_FLAG_EXACT = {
 'CoCreateGuid', 'StringFromGUID2', 'UuidFromStringW', 'UuidFromStringA',
 'OpenProcessToken', 'GetTokenInformation', 'AllocateAndInitializeSid',
 'InitializeSid', 'EqualSid', 'CopySid', 'GetLengthSid', 'FreeSid',
 'InitializeSecurityDescriptor', 'InitializeAcl',
 'CoCreateInstance', 'CoCreateInstanceEx', 'CreateThread', '_beginthreadex',
 'GetProcAddress', 'LoadLibraryA', 'LoadLibraryW', 'LoadLibraryExA', 'LoadLibraryExW',
 'GetVersion', 'GetVersionExA', 'GetVersionExW', 'SHGetFolderPathA', 'SHGetFolderPathW',
 'SHGetSpecialFolderPathA', 'SHGetSpecialFolderPathW', 'GetCommandLineA', 'GetCommandLineW',
 'GetModuleFileNameA', 'GetModuleFileNameW', 'GetModuleHandleA', 'GetModuleHandleW',
 '_getpid', 'FindResourceA', 'FindResourceW', 'LoadResource', 'LockResource', 'SizeofResource',
 'GetDiskFreeSpaceA', 'GetDiskFreeSpaceExA', 'GlobalMemoryStatus', 'GlobalMemoryStatusEx',
 'GetProcessAffinityMask', 'GetSystemInfo', 'GetNativeSystemInfo',
 'time', 'clock', 'GetTickCount', 'timeGetTime', 'QueryPerformanceCounter',
 'QueryPerformanceFrequency', 'GetLocalTime', 'GetSystemTime', 'GetSystemTimeAsFileTime',
 'rand', 'srand', 'localtime', 'gmtime', 'mktime',
 'RegOpenKeyExA', 'RegOpenKeyExW', 'RegOpenKeyA', 'RegQueryValueExA', 'RegQueryValueExW',
 'RegCreateKeyExA', 'RegCreateKeyExW', 'RegSetValueExA', 'GetCurrentProcessId',
 'GetCurrentThreadId', 'GetUserNameA', 'GetUserNameW', 'GetComputerNameA', 'GetComputerNameW',
 'GetVolumeInformationA', 'GetVolumeInformationW', 'DeviceIoControl',
}
def _cb17_name(_full):
    if _full.startswith('GetProcAddress:'): return _full
    return _full.split('!')[-1]
def _cb17_flagged(_full, _handler):
    _nm = _cb17_name(_full)
    if _nm.startswith('GetProcAddress:'): return True
    if _nm in _CB17_FLAG_EXACT: return True
    if getattr(_handler, '__name__', '') in ('h_noop0', 'h_ret1'): return True
    return False
def _cb17_record(_full, _handler, _args, _ret, _retaddr):
    try:
        _win = _CB17['win'] + ('[5170]' if _CB17.get('hdepth', 0) else '')
        _c = _CB17['counts'].setdefault(_win, {})
        _nm = _cb17_name(_full)
        _c[_nm] = _c.get(_nm, 0) + 1
        if _cb17_flagged(_full, _handler):
            _CB17['detail'].append((_win, _full, [hex(v) for v in _args[:6]],
                                    hex(_ret & 0xFFFFFFFF), hex(_retaddr)))
    except Exception:
        pass
ALLOC_LEDGER = []
def log(*a):
    print(*a, flush=True)

# ---------------------------------------------------------------- allocator
class Allocator:
    def __init__(self, uc):
        self.uc = uc
        self.brk = HEAP_BASE
        self.free_list = []       # (addr, size)
        self.live = {}            # addr -> size
    def alloc(self, size, tag=''):
        size = max(16, (size + 15) & ~15)
        for i, (a, s) in enumerate(self.free_list):
            if s >= size:
                if s - size >= 32:
                    self.free_list[i] = (a + size, s - size)
                    got = a
                else:
                    self.free_list.pop(i); got = a; size = s
                self.live[got] = size
                ALLOC_LEDGER.append((got, size, tag))
                return got
        got = self.brk
        self.brk += size
        if self.brk > HEAP_BASE + HEAP_SIZE:
            raise RuntimeError('heap exhausted')
        self.live[got] = size
        ALLOC_LEDGER.append((got, size, tag))
        return got
    def free(self, addr):
        if addr in self.live:
            self.free_list.append((addr, self.live.pop(addr)))
    def realloc(self, addr, size):
        if addr == 0: return self.alloc(size, 'realloc')
        old = self.live.get(addr, 0)
        new = self.alloc(size, 'realloc')
        n = min(old, size)
        if n: self.uc.mem_write(new, self.uc.mem_read(addr, n))
        self.free(addr)
        return new
    def size_of(self, addr):
        return self.live.get(addr, 0)

# ---------------------------------------------------------------- helpers
class Emu:
    def __init__(self):
        self.uc = Uc(UC_ARCH_X86, UC_MODE_32)
        self.alloc = Allocator(self.uc)
        self.stubs = []           # (name, handler, conv, nargs) ; idx0 = halt
        self.stub_by_key = {}
        self.handles = {}         # guest handle -> ('file', hostfile, path) etc.
        self.next_handle = 0x100
        self.last_error = 0
        self.tls_next = 1
        self.tls_vals = {}
        self.tick = 100000
        self.stop_reason = None
        self.reg_keys = {}        # handle -> key path
        self.next_hkey = 0x800
        self.find_handles = {}
        self._map_all()

    # memory primitives
    def rd(self, addr, size):  return bytes(self.uc.mem_read(addr, size))
    def wr(self, addr, data):  self.uc.mem_write(addr, bytes(data))
    def r32(self, addr): return struct.unpack('<I', self.rd(addr, 4))[0]
    def w32(self, addr, v):  self.wr(addr, struct.pack('<I', v & 0xFFFFFFFF))
    def r16(self, addr): return struct.unpack('<H', self.rd(addr, 2))[0]
    def cstr(self, addr, maxn=4096):
        if addr == 0: return ''
        out = bytearray()
        while len(out) < maxn:
            b = self.rd(addr + len(out), 1)[0]
            if b == 0: break
            out.append(b)
        return out.decode('latin-1')
    def wstr(self, addr, maxn=4096):
        if addr == 0: return ''
        out = bytearray()
        while len(out) < maxn * 2:
            v = self.r16(addr + len(out))
            if v == 0: break
            out += struct.pack('<H', v)
        return bytes(out).decode('utf-16-le', 'replace')
    def put_cstr(self, addr, s):
        self.wr(addr, s.encode('latin-1') + b'\0')
    def put_wstr(self, addr, s):
        self.wr(addr, s.encode('utf-16-le') + b'\0\0')

    def _map_all(self):
        uc = self.uc
        uc.mem_map(STACK_BASE, STACK_SIZE)
        uc.mem_map(HEAP_BASE, HEAP_SIZE)
        uc.mem_map(VA_BASE, VA_SIZE)
        uc.mem_map(STUB_BASE, STUB_SIZE)
        uc.mem_write(STUB_BASE, b'\x90' * STUB_SIZE)  # run68: NOP fill, not INT3, so the patch-gate shim stops treating every HLE stub as INT3-patched
        uc.mem_map(0x0, 0x10000)                          # TEB/PEB/AUX pages
        uc.mem_map(EXE_BASE, 0x1000)
        uc.mem_write(EXE_BASE, b'MZ' + b'\0' * 0x100)
        # TEB
        self.w32(TEB_BASE + 0x00, 0xFFFFFFFF)             # SEH chain end
        self.w32(TEB_BASE + 0x04, STACK_BASE + STACK_SIZE)  # stack base
        self.w32(TEB_BASE + 0x08, STACK_BASE)               # stack limit
        self.w32(TEB_BASE + 0x18, TEB_BASE)                 # self
        self.w32(TEB_BASE + 0x2C, AUX_BASE + 0x6000)        # TLS array ptr
        # (was AUX_BASE itself: the array aliased the TEB's first bytes,
        # so guest/HLE TLS writes at slot idx landed on linear idx*4 --
        # slot 0 overwrote the SEH chain head at fs:[0]. Run 51: the
        # final dispatch found head=0 after march 3's TLS traffic.)
        self.w32(TEB_BASE + 0x30, PEB_BASE)                 # PEB
        # PEB + a plausible RTL_USER_PROCESS_PARAMETERS for CRT startup
        self.w32(PEB_BASE + 0x08, EXE_BASE)                 # ImageBaseAddress
        self.w32(PEB_BASE + 0x18, 0x1)                      # ProcessHeap (fake id)
        PARAMS = AUX_BASE + 0x2000
        self.w32(PEB_BASE + 0x10, PARAMS)                   # ProcessParameters
        self.w32(PEB_BASE + 0x0C, AUX_BASE + 0x2C00)        # Ldr (self-linked)
        ldr = AUX_BASE + 0x2C00
        self.w32(ldr + 0x0C, ldr + 0x0C); self.w32(ldr + 0x10, ldr + 0x0C)
        def ustr(at, s, bufat):
            b = s.encode('utf-16-le')
            self.wr(bufat, b + b'\0\0')
            self.wr(at, struct.pack('<HHI', len(b), len(b) + 2, bufat))
        ustr(PARAMS + 0x38, 'C:\\salhost.exe', AUX_BASE + 0x2400)   # ImagePathName
        ustr(PARAMS + 0x40, 'salhost.exe', AUX_BASE + 0x2500)       # CommandLine
        ustr(PARAMS + 0x24, 'C:\\', AUX_BASE + 0x2600)              # CurrentDirectory.DosPath
        self.w32(PARAMS + 0x48, AUX_BASE + 0x2800)                  # Environment (empty block)
        # No segment setup: this Unicorn build refuses data-segment loads,
        # and the default FS base is 0 — which the TEB-at-0 layout exploits.
        self.va_next = VA_BASE

    # ---------------------------------------------------------- stub engine
    def make_stub(self, key, name, handler, conv='stdcall', nargs=0):
        if key in self.stub_by_key:
            return self.stub_by_key[key]
        idx = len(self.stubs)
        self.stubs.append((name, handler, conv, nargs))
        addr = STUB_BASE + idx * 16
        self.stub_by_key[key] = addr
        return addr
    def halt_stub(self):
        return self.make_stub('__halt__', '<halt>', None)

    def on_stub(self, addr):
        idx = (addr - STUB_BASE) // 16
        name, handler, conv, nargs = self.stubs[idx]
        uc = self.uc
        esp = uc.reg_read(UC_X86_REG_ESP)
        retaddr = self.r32(esp)
        if idx == HALT_IDX:
            self.stop_reason = 'halt stub reached'
            uc.emu_stop(); return
        if handler is None:
            self.stop_reason = f'UNIMPLEMENTED import called: {name}'
            TRACE.append(('UNIMPL', name, retaddr))
            uc.emu_stop(); return
        args = [self.r32(esp + 4 + 4 * i) for i in range(12)]
        TRACE.append(('call', name, args[:max(nargs, 1)]))
        self._cur_esp = esp; self._cur_retaddr = retaddr
        try:
            ret = handler(self, args, uc.reg_read(UC_X86_REG_ECX))
        except _CxxThrowSignal:
            # sal_emu157 (Session 20): a C++ throw is pending FH1 dispatch.
            # Record the exact pre-157 end-state string so run_with_seh can
            # restore it verbatim if dispatch finds no handler.
            if getattr(self, 'pending_cxx', None) is not None:
                self.pending_cxx['old_stop'] = (
                    f'handler error in {name}: '
                    f'{RuntimeError("guest called abort/exit")!r}')
            self.stop_reason = 'cxxthrow pending dispatch'
            uc.emu_stop(); return
        except Exception as e:
            self.stop_reason = f'handler error in {name}: {e!r}'
            uc.emu_stop(); return
        if ret is None: ret = 0
        if isinstance(ret, tuple):                        # (eax, edx)
            uc.reg_write(UC_X86_REG_EAX, ret[0] & 0xFFFFFFFF)
            uc.reg_write(UC_X86_REG_EDX, ret[1] & 0xFFFFFFFF)
        else:
            uc.reg_write(UC_X86_REG_EAX, ret & 0xFFFFFFFF)
        _cb17_record(name, handler, args, ret[0] if isinstance(ret, tuple) else ret, retaddr)
        clean = 0 if conv == 'cdecl' else 4 * nargs
        uc.reg_write(UC_X86_REG_ESP, esp + 4 + clean)
        uc.reg_write(UC_X86_REG_EIP, retaddr)

    # ---------------------------------------------------------- PE loading
    def load_pe(self, path, base, resolve_imports):
        pe = pefile.PE(path)
        uc = self.uc
        size = (pe.OPTIONAL_HEADER.SizeOfImage + 0xFFF) & ~0xFFF
        uc.mem_map(base, size)
        hdr = pe.get_memory_mapped_image()[:pe.OPTIONAL_HEADER.SizeOfHeaders]
        uc.mem_write(base, bytes(hdr))
        for sec in pe.sections:
            raw = sec.get_data()
            if raw:
                uc.mem_write(base + sec.VirtualAddress, bytes(raw))
        # relocations (delta from preferred base; ours is 0 but stay correct)
        delta = base - pe.OPTIONAL_HEADER.ImageBase
        if delta != 0 and hasattr(pe, 'DIRECTORY_ENTRY_BASERELOC'):
            for entry in pe.DIRECTORY_ENTRY_BASERELOC:
                for r in entry.entries:
                    if r.type == 3:  # HIGHLOW
                        a = base + r.rva
                        self.w32(a, (self.r32(a) + delta) & 0xFFFFFFFF)
        exports = {}
        if hasattr(pe, 'DIRECTORY_ENTRY_EXPORT'):
            for s in pe.DIRECTORY_ENTRY_EXPORT.symbols:
                if s.name:
                    exports[s.name.decode()] = base + s.address
                if s.ordinal:
                    exports[f'#{s.ordinal}'] = base + s.address
        if resolve_imports:
            for desc in pe.DIRECTORY_ENTRY_IMPORT:
                dll = desc.dll.decode().lower()
                for imp in desc.imports:
                    nm = imp.name.decode() if imp.name else f'#{imp.ordinal}'
                    self.resolve_one(base, imp.address, dll, nm)
        return exports

    def resolve_one(self, mod_base, iat_addr, dll, nm):
        key = f'{dll}!{nm}'
        # real cross-module exports win (OMGUtils for salwrap)
        if key in EXPORTS or nm in EXPORTS:
            self.w32(iat_addr, EXPORTS.get(key, EXPORTS.get(nm))); return
        if key in DATA_IMPORTS:
            cell = self.alloc.alloc(16, f'data:{key}')
            self.wr(cell, DATA_IMPORTS[key])
            self.w32(iat_addr, cell); return
        spec = HLE.get(key) or HLE.get(nm)
        if spec is not None:
            handler, conv, nargs = spec
            self.w32(iat_addr, self.make_stub(key, key, handler, conv, nargs))
        else:
            self.w32(iat_addr, self.make_stub(key, key, None))

    # --------------------------------------------------- SEH support pieces
    def snapshot_ctx(self, ctx, eip, esp):
        uc = self.uc
        self.wr(ctx, b'\0' * 716)
        self.w32(ctx + 0x00, 0x10017)                     # ContextFlags: full+debug
        dr = getattr(self, 'dr', [0] * 8)
        for i, off in enumerate((0x04, 0x08, 0x0C, 0x10, 0x14, 0x18)):
            self.w32(ctx + off, (dr[0], dr[1], dr[2], dr[3], dr[6], dr[7])[i])
        # TRUE x86 CONTEXT layout: segs 0x8C.., Edi 0x9C, Esi 0xA0, Ebx 0xA4,
        # Edx 0xA8, Ecx 0xAC, Eax 0xB0, Ebp 0xB4, Eip 0xB8, SegCs 0xBC,
        # EFlags 0xC0, Esp 0xC4, SegSs 0xC8.
        w = lambda off, v: self.w32(ctx + off, v)
        w(0x8C, 0x2B); w(0x90, 0x53); w(0x94, 0x2B); w(0x98, 0x2B)
        w(0x9C, uc.reg_read(UC_X86_REG_EDI)); w(0xA0, uc.reg_read(UC_X86_REG_ESI))
        w(0xA4, uc.reg_read(UC_X86_REG_EBX)); w(0xA8, uc.reg_read(UC_X86_REG_EDX))
        w(0xAC, uc.reg_read(UC_X86_REG_ECX)); w(0xB0, uc.reg_read(UC_X86_REG_EAX))
        w(0xB4, uc.reg_read(UC_X86_REG_EBP)); w(0xB8, eip); w(0xBC, 0x23)
        w(0xC0, uc.reg_read(UC_X86_REG_EFLAGS)); w(0xC4, esp); w(0xC8, 0x2B)
    def apply_ctx(self, ctx):
        uc = self.uc
        g = lambda off: self.r32(ctx + off)
        uc.reg_write(UC_X86_REG_EDI, g(0x9C)); uc.reg_write(UC_X86_REG_ESI, g(0xA0))
        uc.reg_write(UC_X86_REG_EBX, g(0xA4)); uc.reg_write(UC_X86_REG_EDX, g(0xA8))
        uc.reg_write(UC_X86_REG_ECX, g(0xAC)); uc.reg_write(UC_X86_REG_EAX, g(0xB0))
        uc.reg_write(UC_X86_REG_EBP, g(0xB4))
        uc.reg_write(UC_X86_REG_EFLAGS, g(0xC0) | 2)
        uc.reg_write(UC_X86_REG_ESP, g(0xC4))
        return g(0xB8)
    def raw_call(self, fn, args, label='seh'):
        """Call fn(args...) at the CURRENT stack position (for SEH handlers)."""
        uc = self.uc
        esp = uc.reg_read(UC_X86_REG_ESP) - 0x40
        halt = self.halt_stub()
        try:
            self.w32(esp, halt)
            for i, a in enumerate(args):
                self.w32(esp + 4 + 4 * i, a)
        except UcError:
            # Faulting ESP is wild/unmapped (e.g. the fault WAS a stack
            # push past the edge). The OS guarantees the dispatcher a
            # runnable stack; emulate that with a scratch stack in AUX.
            esp = 0xDFF0
            self.w32(esp, halt)
            for i, a in enumerate(args):
                self.w32(esp + 4 + 4 * i, a)
        uc.reg_write(UC_X86_REG_ESP, esp)
        # The OS delivers exceptions with TF clear in the handler's live
        # flags (TF survives only inside the saved CONTEXT). Without this,
        # a guest-set trap flag single-steps the handler itself to death.
        uc.reg_write(UC_X86_REG_EFLAGS, uc.reg_read(UC_X86_REG_EFLAGS) & ~0x100)
        self.stop_reason = None
        try:
            uc.emu_start(fn, halt, count=0)
        except UcError as ex:
            self.stop_reason = (f'UcError {ex} during {label} at '
                                f'EIP={uc.reg_read(UC_X86_REG_EIP):#x}')
        return uc.reg_read(UC_X86_REG_EAX)

    # ---------------------------------------------------------- execution
    def call(self, addr, args=(), ecx=None, label=''):
        uc = self.uc
        esp = STACK_BASE + STACK_SIZE - 0x1000
        for i, a in enumerate(args):
            self.w32(esp + 4 + 4 * i, a)
        halt = self.halt_stub()
        self.w32(esp, halt)
        uc.reg_write(UC_X86_REG_ESP, esp)
        if ecx is not None:
            uc.reg_write(UC_X86_REG_ECX, ecx)
        self.stop_reason = None
        try:
            uc.emu_start(addr, halt, count=0)
        except UcError as e:
            self.stop_reason = f'UcError {e} during {label}'
        eax = uc.reg_read(UC_X86_REG_EAX)
        if self.stop_reason:
            log(f'  [{label}] stopped: {self.stop_reason}')
        return eax

EXPORTS = {}
DATA_IMPORTS = {
    'msvcp71.dll!?npos@?$basic_string@DU?$char_traits@D@std@@V?$allocator@D@2@@std@@2IB':
        struct.pack('<I', 0xFFFFFFFF),
    'msvcp71.dll!?npos@?$basic_string@GU?$char_traits@G@std@@V?$allocator@G@2@@std@@2IB':
        struct.pack('<I', 0xFFFFFFFF),
}
HLE = {}   # filled by hle tables below (key 'dll!name' or bare 'name' -> (fn, conv, nargs))

# ================================================================ CRT (HLE)
def _fmt(e, fmt, args, wide=False):
    """Minimal printf formatter. args = list of stack slots (ints)."""
    out = []
    ai = 0
    i = 0
    while i < len(fmt):
        c = fmt[i]
        if c != '%':
            out.append(c); i += 1; continue
        i += 1
        if i < len(fmt) and fmt[i] == '%':
            out.append('%'); i += 1; continue
        flags = ''
        while i < len(fmt) and fmt[i] in '-+ #0':
            flags += fmt[i]; i += 1
        width = ''
        while i < len(fmt) and fmt[i].isdigit():
            width += fmt[i]; i += 1
        prec = None
        if i < len(fmt) and fmt[i] == '.':
            i += 1; prec = ''
            while i < len(fmt) and fmt[i].isdigit():
                prec += fmt[i]; i += 1
        lng = ''
        while i < len(fmt) and fmt[i] in 'lhI':
            lng += fmt[i]; i += 1
        if i >= len(fmt): break
        conv = fmt[i]; i += 1
        a = args[ai] if ai < len(args) else 0
        if conv in 'di':
            v = a - (1 << 32) if a >= (1 << 31) else a
            s = str(v); ai += 1
        elif conv == 'u':
            s = str(a); ai += 1
        elif conv in 'xX':
            s = format(a, 'x' if conv == 'x' else 'X'); ai += 1
            if '#' in flags: s = '0x' + s
        elif conv == 'o':
            s = format(a, 'o'); ai += 1
        elif conv == 'p':
            s = format(a, '08X'); ai += 1
        elif conv == 'c':
            s = chr(a & 0xFF); ai += 1
        elif conv == 's':
            s = e.wstr(a) if (wide or 'l' in lng or 'w' in lng) else e.cstr(a)
            ai += 1
            if prec not in (None, ''): s = s[:int(prec)]
        elif conv in 'feEgG':
            # float args live on the stack as doubles (8 bytes, 2 slots)
            lo = a; hi = args[ai + 1] if ai + 1 < len(args) else 0
            v = struct.unpack('<d', struct.pack('<II', lo, hi))[0]
            s = ('%g' % v) if conv in 'gG' else ('%f' % v)
            ai += 2
        else:
            s = '%' + conv
        w = int(width) if width else 0
        if len(s) < w:
            pad = '0' if ('0' in flags and '-' not in flags and conv in 'diuxXop') else ' '
            s = (s + pad * (w - len(s))) if '-' in flags else (pad * (w - len(s)) + s)
        out.append(s)
    return ''.join(out)

def h_malloc(e, a, x):   return e.alloc.alloc(a[0], 'malloc')
def h_calloc(e, a, x):   
    p = e.alloc.alloc(a[0] * a[1], 'calloc'); e.wr(p, b'\0' * (a[0] * a[1])); return p
def h_realloc(e, a, x):  return e.alloc.realloc(a[0], a[1])
def h_free(e, a, x):     e.alloc.free(a[0]); return 0
def h_new(e, a, x):      return e.alloc.alloc(a[0], 'operator new')
def h_memcpy(e, a, x):
    if a[2]: e.wr(a[0], e.rd(a[1], a[2]))
    return a[0]
def h_memset(e, a, x):
    if a[2]: e.wr(a[0], bytes([a[1] & 0xFF]) * a[2])
    return a[0]
def h_memcmp(e, a, x):
    b1, b2 = e.rd(a[0], a[2]), e.rd(a[1], a[2])
    return 0 if b1 == b2 else (1 if b1 > b2 else -1)
def h_memchr(e, a, x):
    buf = e.rd(a[0], a[2])
    i = buf.find(bytes([a[1] & 0xFF]))
    return a[0] + i if i >= 0 else 0
def h_strlen(e, a, x):   return len(e.cstr(a[0]))
def h_strcpy(e, a, x):
    s = e.cstr(a[1]); e.put_cstr(a[0], s); return a[0]
def h_strncpy(e, a, x):
    s = e.cstr(a[1])[:a[2]]; e.wr(a[0], s.encode('latin-1') + b'\0' * (a[2] - len(s))); return a[0]
def h_strcat(e, a, x):
    d = e.cstr(a[0]); s = e.cstr(a[1]); e.put_cstr(a[0], d + s); return a[0]
def h_strcmp(e, a, x):
    s1, s2 = e.cstr(a[0]), e.cstr(a[1])
    return 0 if s1 == s2 else (1 if s1 > s2 else -1)
def h_strncmp(e, a, x):
    s1, s2 = e.cstr(a[0])[:a[2]], e.cstr(a[1])[:a[2]]
    return 0 if s1 == s2 else (1 if s1 > s2 else -1)
def h_stricmp(e, a, x):
    s1, s2 = e.cstr(a[0]).lower(), e.cstr(a[1]).lower()
    return 0 if s1 == s2 else (1 if s1 > s2 else -1)
def h_strchr(e, a, x):
    s = e.cstr(a[0]); i = s.find(chr(a[1] & 0xFF))
    return a[0] + i if i >= 0 else 0
def h_strrchr(e, a, x):
    s = e.cstr(a[0]); i = s.rfind(chr(a[1] & 0xFF))
    return a[0] + i if i >= 0 else 0
def h_strstr(e, a, x):
    s, n = e.cstr(a[0]), e.cstr(a[1]); i = s.find(n)
    return a[0] + i if i >= 0 else 0
_STRTOK_NEXT = [0]
def h_strtok(e, a, x):
    # run106: strtok(str, delim) with static continuation pointer (was UNIMPLEMENTED,
    # halted the b650 probe in run95 after the SID classification).
    delim = set(e.cstr(a[1]).encode('latin-1')) if a[1] else set()
    p = a[0] if a[0] else _STRTOK_NEXT[0]
    if not p:
        return 0
    while True:
        b = e.rd(p, 1)
        if not b or b[0] not in delim:
            break
        p += 1
    if not e.rd(p, 1):
        _STRTOK_NEXT[0] = 0
        return 0
    start = p
    while True:
        b = e.rd(p, 1)
        if not b or b[0] in delim:
            break
        p += 1
    if b and b[0] in delim:
        e.wr(p, b'\0')
        _STRTOK_NEXT[0] = p + 1
    else:
        _STRTOK_NEXT[0] = 0
    try:
        log(f'  [strtok] str={a[0]:#x} delim={e.cstr(a[1])!r} -> token={e.cstr(start)!r} next={_STRTOK_NEXT[0]:#x}')
    except Exception:
        pass
    return start
def h_strdup(e, a, x):
    s = e.cstr(a[0]); p = e.alloc.alloc(len(s) + 1, 'strdup'); e.put_cstr(p, s); return p
def h_sprintf(e, a, x):
    s = _fmt(e, e.cstr(a[1]), a[2:]); e.put_cstr(a[0], s); return len(s)
def h_snprintf(e, a, x):
    s = _fmt(e, e.cstr(a[2]), a[3:])
    if a[1]: e.wr(a[0], s[:a[1] - 1].encode('latin-1') + b'\0')
    return len(s)
def h_vsprintf(e, a, x):
    # va_list == pointer to arg array in guest memory
    va = a[2]; args = [e.r32(va + 4 * i) for i in range(10)]
    s = _fmt(e, e.cstr(a[1]), args); e.put_cstr(a[0], s); return len(s)
def h_vsnprintf(e, a, x):
    va = a[3]; args = [e.r32(va + 4 * i) for i in range(10)]
    s = _fmt(e, e.cstr(a[2]), args)
    if a[1]: e.wr(a[0], s[:a[1] - 1].encode('latin-1') + b'\0')
    return len(s)
def h_printf(e, a, x):
    s = _fmt(e, e.cstr(a[0]), a[1:]); log('  [guest printf]', s); return len(s)
def h_fprintf(e, a, x):
    s = _fmt(e, e.cstr(a[1]), a[2:]); log('  [guest fprintf]', s); return len(s)
def h_noop0(e, a, x):    return 0
def h_ret1(e, a, x):     return 1
def h_except_handler3(e, a, x):
    # run106: real _except_handler3 scope handling (was h_ret1 = always
    # CONTINUE_SEARCH, which dropped every __try/__except filter). SEH frame:
    # [frame+0]=prev, [frame+4]=handler, [frame+8]=scope table, [frame+12]=try level.
    # Scope records here are 12 bytes {enclosing, filter, handler} — verified
    # against OMGUtils table 0x63923c00, record 0 = {-1, 0x6391a055, 0x6391a069}.
    # Narrow gate: only breakpoint faults whose filter bytes match the known
    # breakpoint filter (mov eax,[ebp-0x14]; mov ecx,[eax]; mov eax,[ecx];
    # xor edx,edx; cmp eax,0x80000003; sete dl) transfer to the handler block;
    # everything else keeps the old CONTINUE_SEARCH behavior.
    try:
        _rec, _frame, _ctx = a[0], a[1], a[2]
        _code = e.r32(_rec)
        _tl = e.r32(_frame + 12)
        if _tl < 0 or _tl > 0x1000:
            return 1
        _tbl = e.r32(_frame + 8)
        _r = _tbl + _tl * 12
        _enc, _flt, _hdl = e.r32(_r), e.r32(_r + 4), e.r32(_r + 8)
        log(f'  [eh3] frame={_frame:#x} trylevel={_tl} scope={_tbl:#x} '
            f'enc={_enc} filter={_flt:#x} handler={_hdl:#x} code={_code:#x}')
        if _code != 0x80000003:
            return 1
        try:
            _fb = e.rd(_flt, 17)  # run106 FIX: the filter prologue is 17 bytes, not 16 (run91 compared 16 bytes against a 17-byte pattern and always missed)
        except Exception:
            return 1
        if _fb.hex() != '8b45ec8b088b0133d23d030000800f94c2':
            return 1
        if not (0x63900000 <= _hdl < 0x63a00000 or 0x65100000 <= _hdl < 0x65200000):
            return 1
        log(f'  [eh3] breakpoint filter MATCHED; transferring to handler {_hdl:#x}')
        e.w32(_ctx + 0xB8, _hdl)  # CTX.Eip = handler block (a069: unwinds, returns flag)
        return 0
    except Exception as _ex:
        log(f'  [eh3] failed: {_ex!r}')
        return 1
def h_atoi(e, a, x):
    try: return int(e.cstr(a[0]).strip() or 0)
    except ValueError: return 0
def h_atol(e, a, x):     return h_atoi(e, a, x)
def h_strtol(e, a, x):
    s = e.cstr(a[0]).lstrip()
    try: v = int(s.split()[0], a[2] if a[2] else 10)
    except Exception: v = 0
    return v
def h_tolower(e, a, x):  return ord(chr(a[0] & 0xFF).lower())
def h_toupper(e, a, x):  return ord(chr(a[0] & 0xFF).upper())
def h_abs(e, a, x):
    v = a[0] - (1 << 32) if a[0] >= (1 << 31) else a[0]
    return abs(v)
def h_time(e, a, x):
    import time as _t
    v = 1793313847  # run152 FROZEN (was int(_t.time()))
    if a[0]: e.w32(a[0], v)
    return v
def h_clock(e, a, x):
    e.tick += 1000; return e.tick
def h_qsort(e, a, x):
    log('  [hle] qsort: left unsorted (comparator is guest code)')
    return 0
def h_abort(e, a, x):
    raise RuntimeError('guest called abort/exit')
class _CxxThrowSignal(Exception):
    # sal_emu157 (Session 20): raised by the _CxxThrowException HLE to hand
    # the pending throw to the top-level FH1 dispatcher in run_with_seh.
    # HLE handlers run inside a code hook and cannot execute guest code
    # (unwind funclets / catch blocks), so dispatch cannot happen here.
    pass

def h_cxxthrow_capture(e, a, x):
    # run155 (Session 18): CAPTURE _CxxThrowException(pExceptionObject, pThrowInfo)
    # -- throw site, exception-object fields, ThrowInfo catchable types, and the
    # live SEH chain. sal_emu157 (Session 20): after capturing, record the
    # pending throw on the Emu and raise _CxxThrowSignal; run_with_seh runs
    # the table-driven FH1 dispatch at top level. If dispatch finds no
    # handler anywhere, the phase ends with the EXACT pre-157 stop string
    # (reconstructed in on_stub), so no-catch chains are unchanged.
    _ret = getattr(e, '_cur_retaddr', 0)
    def _mod(_v):
        for _lo, _hi, _nm in ((0x65100000, 0x65177000, 'salwrap'), (0x64700000, 0x64732000, 'pfcom'),
                              (0x63900000, 0x63933000, 'OMGUtils'), (0x10000000, 0x12000000, 'heap'),
                              (0x0F3FE000, 0x0F400000, 'stack')):
            if _lo <= _v < _hi: return _nm
        return '?'
    try:
        _obj, _ti = a[0], a[1]
        log(f'  [cxxthrow] retaddr={_ret:#x} ({_mod(_ret)}) obj={_obj:#x} throwinfo={_ti:#x} esp={getattr(e, "_cur_esp", 0):#x}')
        if _obj:
            _ob = e.rd(_obj, 0x60)
            log(f'  [cxxthrow] obj[0:0x60]: {_ob.hex(" ")}')
            _vt = e.r32(_obj)
            log(f'  [cxxthrow] obj vtable={_vt:#x} ({_mod(_vt)})')
        if _ti:
            _attr, _unw, _fwd, _cta = e.r32(_ti), e.r32(_ti + 4), e.r32(_ti + 8), e.r32(_ti + 12)
            log(f'  [cxxthrow] TI attr={_attr:#x} unwind={_unw:#x}({_mod(_unw)}) fwd={_fwd:#x} cta={_cta:#x}')
            if _cta:
                _n = e.r32(_cta)
                log(f'  [cxxthrow] catchable types: {_n}')
                for _i in range(min(_n, 8)):
                    _ct = e.r32(_cta + 4 + 4 * _i)
                    _td = e.r32(_ct + 4)
                    _nm = ''
                    try: _nm = e.cstr(_td + 8)
                    except Exception: pass
                    log(f'  [cxxthrow]   CT[{_i}] @{_ct:#x} props={e.r32(_ct):#x} typedesc={_td:#x} name={_nm!r}')
        _esp = getattr(e, '_cur_esp', 0)
        if _esp:
            _sb = e.rd(_esp, 0x100)
            _cands = []
            for _o in range(0, 0x100, 4):
                _v = int.from_bytes(_sb[_o:_o + 4], 'little')
                if _mod(_v) in ('salwrap', 'pfcom', 'OMGUtils'):
                    _cands.append(f'esp+{_o:#x}={_v:#x}({_mod(_v)})')
            log('  [cxxthrow] stack module-ptrs: ' + ' '.join(_cands))
        _node = e.r32(0)
        _d = 0
        while _node and _node != 0xFFFFFFFF and _d < 24:
            _h = e.r32(_node + 4)
            log(f'  [cxxthrow] SEH node[{_d}] @{_node:#x} handler={_h:#x} ({_mod(_h)})')
            _node = e.r32(_node); _d += 1
    except Exception as _ex:
        log(f'  [cxxthrow] capture failed: {_ex!r}')
    # sal_emu157: hand the throw to the top-level FH1 dispatcher.
    _uc = e.uc
    e.pending_cxx = {
        'obj': a[0], 'ti': a[1],
        'retaddr': getattr(e, '_cur_retaddr', 0),
        'esp': getattr(e, '_cur_esp', 0),
        'regs': {r: _uc.reg_read(r) for r in (
            UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDX,
            UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP, UC_X86_REG_EFLAGS)},
    }
    raise _CxxThrowSignal()
INITQ = []
def h_initterm(e, a, x):
    # Handlers cannot call guest code mid-hook; queue the table and let the
    # runner drain it between top-level calls (DllMain returns fine without
    # the ctors having run yet; the users of the statics come later).
    INITQ.append((a[0], a[1]))
    log(f'  [hle] _initterm({a[0]:#x},{a[1]:#x}) queued')
    return 0
def h_ftol(e, a, x):
    raw = e.uc.reg_read(UC_X86_REG_ST0)
    if isinstance(raw, int):
        return raw & 0xFFFFFFFF
    b = raw if isinstance(raw, bytes) else bytes(raw)
    try:
        import numpy as _np
        v = float(_np.frombuffer(b[:10], dtype=_np.float80)[0])
    except Exception:
        v = 0.0
    return int(v) & 0xFFFFFFFF

CRT = {
 'malloc': (h_malloc, 'cdecl', 1), 'calloc': (h_calloc, 'cdecl', 2),
 'realloc': (h_realloc, 'cdecl', 2), 'free': (h_free, 'cdecl', 1),
 '_malloc': (h_malloc, 'cdecl', 1), '_free': (h_free, 'cdecl', 1),
 'memcpy': (h_memcpy, 'cdecl', 3), 'memmove': (h_memcpy, 'cdecl', 3),
 'memset': (h_memset, 'cdecl', 3), 'memcmp': (h_memcmp, 'cdecl', 3),
 'memchr': (h_memchr, 'cdecl', 3),
 'strlen': (h_strlen, 'cdecl', 1), 'strcpy': (h_strcpy, 'cdecl', 2),
 'strncpy': (h_strncpy, 'cdecl', 3), 'strcat': (h_strcat, 'cdecl', 2),
 'strncat': (h_strcat, 'cdecl', 3), 'strcmp': (h_strcmp, 'cdecl', 2),
 'strncmp': (h_strncmp, 'cdecl', 3), '_stricmp': (h_stricmp, 'cdecl', 2),
 '_strcmpi': (h_stricmp, 'cdecl', 2), 'stricmp': (h_stricmp, 'cdecl', 2),
 'strchr': (h_strchr, 'cdecl', 2), 'strrchr': (h_strrchr, 'cdecl', 2),
 'strstr': (h_strstr, 'cdecl', 2), 'strtok': (h_strtok, 'cdecl', 2), '_strdup': (h_strdup, 'cdecl', 1),
 'strdup': (h_strdup, 'cdecl', 1),
 'sprintf': (h_sprintf, 'cdecl', 2), '_snprintf': (h_snprintf, 'cdecl', 3),
 'snprintf': (h_snprintf, 'cdecl', 3),
 'vsprintf': (h_vsprintf, 'cdecl', 3), '_vsnprintf': (h_vsnprintf, 'cdecl', 4),
 'vsnprintf': (h_vsnprintf, 'cdecl', 4),
 'printf': (h_printf, 'cdecl', 1), 'fprintf': (h_fprintf, 'cdecl', 2),
 'atoi': (h_atoi, 'cdecl', 1), 'atol': (h_atol, 'cdecl', 1),
 'strtol': (h_strtol, 'cdecl', 3), 'strtoul': (h_strtol, 'cdecl', 3),
 'tolower': (h_tolower, 'cdecl', 1), 'toupper': (h_toupper, 'cdecl', 1),
 'abs': (h_abs, 'cdecl', 1), 'labs': (h_abs, 'cdecl', 1),
 'time': (h_time, 'cdecl', 1), 'clock': (h_clock, 'cdecl', 0),
 'qsort': (h_qsort, 'cdecl', 4),
 'abort': (h_abort, 'cdecl', 0), 'exit': (h_abort, 'cdecl', 1),
 '_initterm': (h_initterm, 'cdecl', 2), '_initterm_e': (h_initterm, 'cdecl', 2),
 'atexit': (h_noop0, 'cdecl', 1), '_onexit': (h_noop0, 'cdecl', 1),
 '__dllonexit': (h_noop0, 'cdecl', 3),
 '_except_handler3': (h_except_handler3, 'cdecl', 4), '__CxxFrameHandler': (h_ret1, 'cdecl', 4),
 '_except_handler4': (h_ret1, 'cdecl', 5),
 '_CxxThrowException': (h_cxxthrow_capture, 'cdecl', 2),
 '_ftol': (h_ftol, 'cdecl', 0),
 '??2@YAPAXI@Z': (h_new, 'cdecl', 1),                       # operator new
 '??3@YAXPAX@Z': (h_free, 'cdecl', 1),                      # operator delete
 '??_U@YAPAXI@Z': (h_new, 'cdecl', 1),                      # operator new[]
 '??_V@YAXPAX@Z': (h_free, 'cdecl', 1),                     # operator delete[]
 '_encoded_null': (h_noop0, 'cdecl', 0),
}
HLE.update(CRT)

# ===================================================== MSVC71 std::string
# layout (proven from OMGUtils inline code): +0 alloc, +4 _Bx(_Ptr|_Buf[16B]),
# +0x14 _Mysize, +0x18 _Myres ; SSO iff _Myres < 16/elemcap-units
def _sso(e, o, elem):   return e.r32(o + 0x18) < (16 // elem)
def _sbuf(e, o, elem):  return e.r32(o + 4) if not _sso(e, o, elem) else o + 4
def _sdata(e, o, elem):
    n = e.r32(o + 0x14)
    raw = e.rd(_sbuf(e, o, elem), n * elem)
    return raw.decode('utf-16-le' if elem == 2 else 'latin-1')
def _sset(e, o, s, elem):
    enc = s.encode('utf-16-le' if elem == 2 else 'latin-1')
    n = len(enc) // elem
    cap = (16 // elem) - 1
    res = e.r32(o + 0x18)
    if n > res:
        newres = max(n, res + res // 2, cap)
        nb = e.alloc.alloc((newres + 1) * elem, 'std::string buf')
        if not _sso(e, o, elem): e.alloc.free(e.r32(o + 4))
        e.w32(o + 4, nb); e.w32(o + 0x18, newres)
    buf = _sbuf(e, o, elem)
    e.wr(buf, enc); e.wr(buf + n * elem, b'\0' * elem)
    e.w32(o + 0x14, n)
def _sappend(e, o, s, elem):
    _sset(e, o, _sdata(e, o, elem) + s, elem)
def _sinit(e, o, elem):
    e.w32(o + 0x00, 0); e.w32(o + 0x14, 0)
    e.w32(o + 0x18, (16 // elem) - 1); e.wr(o + 4, b'\0' * elem)

def mk_str_handlers(elem):
    rd = (lambda e, a: e.wstr(a)) if elem == 2 else (lambda e, a: e.cstr(a))
    def ctor_cstr(e, a, x):   _sinit(e, x, elem); _sset(e, x, rd(e, a[0]) if a[0] else '', elem); return x
    def ctor_copy(e, a, x):   _sinit(e, x, elem); _sset(e, x, _sdata(e, a[0], elem), elem); return x
    def ctor_def(e, a, x):    _sinit(e, x, elem); return x
    def dtor(e, a, x):
        if not _sso(e, x, elem): e.alloc.free(e.r32(x + 4))
        e.w32(x + 0x14, 0); e.w32(x + 0x18, 0); return 0
    def assign_str(e, a, x):  _sset(e, x, _sdata(e, a[0], elem), elem); return x
    def assign_cstr(e, a, x): _sset(e, x, rd(e, a[0]) if a[0] else '', elem); return x
    def assign_n(e, a, x):    _sset(e, x, rd(e, a[0])[:a[1]] if a[0] else '', elem); return x
    def append_cstr(e, a, x): _sappend(e, x, rd(e, a[0]) if a[0] else '', elem); return x
    def append_str(e, a, x):  _sappend(e, x, _sdata(e, a[0], elem), elem); return x
    def c_str(e, a, x):       return _sbuf(e, x, elem)
    def erase(e, a, x):
        s = _sdata(e, x, elem); off, cnt = a[0], a[1]
        if off <= len(s):
            cnt = len(s) - off if cnt >= len(s) else cnt
            _sset(e, x, s[:off] + s[off + cnt:], elem)
        return x
    def find_ch(e, a, x):
        s = _sdata(e, x, elem); ch = chr(a[0] & (0xFFFF if elem == 2 else 0xFF))
        i = s.find(ch, a[1]); return i if i >= 0 else 0xFFFFFFFF
    def find_last_of(e, a, x):
        s = _sdata(e, x, elem); chars = rd(e, a[0]); off = a[1]
        off = min(off, len(s) - 1) if s else 0
        for i in range(off, -1, -1):
            if s[i] in chars: return i
        return 0xFFFFFFFF
    def substr(e, a, x):
        s = _sdata(e, x, elem)
        _sinit(e, a[0], elem); _sset(e, a[0], s[a[1]:a[1] + a[2]], elem)
        return a[0]
    return dict(ctor_cstr=ctor_cstr, ctor_copy=ctor_copy, ctor_def=ctor_def,
                dtor=dtor, assign_str=assign_str, assign_cstr=assign_cstr,
                assign_n=assign_n, append_cstr=append_cstr, append_str=append_str,
                c_str=c_str, erase=erase, find_ch=find_ch,
                find_last_of=find_last_of, substr=substr)

def _throw(e, a, x):
    raise RuntimeError('std::_Xlen/_Xran/_Nomemory called (string throw)')

for elem, E in ((1, 'D'), (2, 'G')):
    H = mk_str_handlers(elem)
    T = f'?$basic_string@{E}U?$char_traits@{E}@std@@V?$allocator@{E}@2@@std@@'
    HLE[f'??0{T}QAE@PB{E}@Z'] = (H['ctor_cstr'], 'thiscall', 1)
    HLE[f'??0{T}QAE@ABV01@@Z'] = (H['ctor_copy'], 'thiscall', 1)
    HLE[f'??0{T}QAE@XZ'] = (H['ctor_def'], 'thiscall', 0)
    HLE[f'??1{T}QAE@XZ'] = (H['dtor'], 'thiscall', 0)
    HLE[f'??4{T}QAEAAV01@ABV01@@Z'] = (H['assign_str'], 'thiscall', 1)
    HLE[f'??4{T}QAEAAV01@PB{E}@Z'] = (H['assign_cstr'], 'thiscall', 1)
    HLE[f'?assign@{T}QAEAAV12@PB{E}I@Z'] = (H['assign_n'], 'thiscall', 2)
    HLE[f'??Y{T}QAEAAV01@PB{E}@Z'] = (H['append_cstr'], 'thiscall', 1)
    HLE[f'??Y{T}QAEAAV01@ABV01@@Z'] = (H['append_str'], 'thiscall', 1)
    HLE[f'?c_str@{T}QBEPB{E}XZ'] = (H['c_str'], 'thiscall', 0)
    HLE[f'?erase@{T}QAEAAV12@II@Z'] = (H['erase'], 'thiscall', 2)
    HLE[f'?find@{T}QBEI{E}I@Z'] = (H['find_ch'], 'thiscall', 2)
    HLE[f'?find_last_of@{T}QBEIPB{E}I@Z'] = (H['find_last_of'], 'thiscall', 2)
    HLE[f'?substr@{T}QBE?AV12@II@Z'] = (H['substr'], 'thiscall', 3)
HLE['?_Xlen@_String_base@std@@QBEXXZ'] = (_throw, 'thiscall', 0)
HLE['?_Xran@_String_base@std@@QBEXXZ'] = (_throw, 'thiscall', 0)
HLE['?_Nomemory@std@@YAXXZ'] = (_throw, 'cdecl', 0)
def _op_lt(e, a, x):
    s1 = _sdata(e, a[0], 1); s2 = _sdata(e, a[1], 1)
    return 1 if s1 < s2 else 0
HLE['??$?MDU?$char_traits@D@std@@V?$allocator@D@1@@std@@YA_NABV?$basic_string@DU?$char_traits@D@std@@V?$allocator@D@2@@0@0@Z'] = (_op_lt, 'cdecl', 2)

# ================================================================ Win32 HLE
import os as _os
def _ci_resolve(p):
    # run152: Windows path lookup is CASE-INSENSITIVE; the host FS
    # is not. Through run 148 a guest probe for 'EKB' missed the
    # on-disk 'ekb' directory (and any other case-variant name).
    # If the exact path does not exist, resolve each component
    # against the on-disk entries; a miss on the FINAL component
    # (a file about to be created) keeps the caller's spelling
    # under the resolved parent. Only converts lookups that
    # currently fail; exact hits are returned untouched.
    if _os.path.exists(p):
        return p
    parts = [q for q in p.split('/') if q]
    cur = '/' if p.startswith('/') else ''
    for i, part in enumerate(parts):
        cand = _os.path.join(cur, part) if cur else part
        if _os.path.exists(cand):
            cur = cand
            continue
        try:
            names = _os.listdir(cur or '.')
        except OSError:
            return p
        hit = next((n for n in names if n.lower() == part.lower()), None)
        if hit is not None:
            cur = _os.path.join(cur, hit) if cur else hit
            continue
        if i == len(parts) - 1:
            return _os.path.join(cur, part) if cur else part
        return p
    return cur

def host_path(win):
    w = win.replace('/', '\\')
    lw = w.lower()
    for pre, host in sorted(HOST_FS.items(), key=lambda kv: -len(kv[0])):
        if lw.startswith(pre):
            # run152 FIX: strip leading separators from rest. Through
            # run 147 a rest beginning with '/' made os.path.join
            # DISCARD the host base, so every Repository-relative
            # guest path ('REPO\maclist.dat', 'REPO/procfile/', ...)
            # resolved to the host filesystem root instead of the
            # repository. Windows semantics: the guest path is
            # absolute under its prefix; the remainder is relative.
            rest = w[len(pre):].replace('\\', '/').lstrip('/')
            return _ci_resolve(_os.path.join(host, rest))
    return None

_FETCH = {'cb': None, 'rd': None}   # run109: per-run fetch trace callbacks

# ---- run152: session-create-window access audit (passive logging only)
_AUDIT = {'on': False, 'rows': []}
def _audit(kind, **kw):
    if _AUDIT['on']:
        _AUDIT['rows'].append((kind, kw))
        log('  [audit150] ' + kind + ' ' + ' '.join(f'{k}={v!r}' for k, v in kw.items()))
def _md5(b):
    import hashlib as _hl
    return _hl.md5(b).hexdigest()

def h_CreateFileA(e, a, x):
    path = e.cstr(a[0])
    if _FETCH['cb'] is not None: _FETCH['cb'](e, path)
    hp = host_path(path)
    if hp is None:
        _audit('CreateFile', win=path, host=None, access=hex(a[1]), disp=a[4], result='FAIL-noresolve')
        e.last_error = 3; return 0xFFFFFFFF
    access, disp = a[1], a[4]
    write = bool(access & 0xC0000000)
    _pre = _os.path.exists(hp)
    _psz = _os.path.getsize(hp) if _pre else None
    try:
        if disp == 2 or (disp in (1, 4) and not _os.path.exists(hp)):  # CREATE_ALWAYS/NEW/OPEN_ALWAYS-new
            fh = open(hp, 'w+b')
        elif write:
            fh = open(hp, 'r+b') if _os.path.exists(hp) else open(hp, 'w+b')
        else:
            fh = open(hp, 'rb')
    except OSError:
        _audit('CreateFile', win=path, host=hp, access=hex(access), disp=disp, existed=_pre, size=_psz, result='FAIL-oserror')
        e.last_error = 2; return 0xFFFFFFFF
    h = e.next_handle; e.next_handle += 4
    e.handles[h] = ('file', fh, path)
    _audit('CreateFile', win=path, host=hp, access=hex(access), disp=disp, existed=_pre, size=_psz, result=f'handle={h:#x}')
    log(f'  [file150] CreateFile handle={h:#x} win={path!r} host={hp!r} access={access:#x} disp={disp}')
    return h
def h_CreateFileW(e, a, x):
    class A: pass
    w = e.wstr(a[0])
    p = e.alloc.alloc(len(w) + 1, 'tmp path'); e.put_cstr(p, w)
    return h_CreateFileA(e, [p, a[1], a[2], a[3], a[4], a[5], a[6]], x)
def h_ReadFile(e, a, x):
    ent = e.handles.get(a[0])
    if not ent or ent[0] != 'file': e.last_error = 6; return 0
    data = ent[1].read(a[2])
    _audit('ReadFile', win=ent[2], handle=hex(a[0]), n=a[2], got=len(data), md5=_md5(data) if data else None, hex=data[:100].hex(' ') if 0 < len(data) <= 128 else None)
    if a[2] >= 40: log(f'  [file150] ReadFile handle={a[0]:#x} win={ent[2]!r} dst={a[1]:#x} n={a[2]} got={len(data)} data={data[:100].hex(" ")}')
    if data: e.wr(a[1], data)
    if a[3]: e.w32(a[3], len(data))
    if _FETCH['rd'] is not None: _FETCH['rd'](e, ent[2], a[1], len(data))
    return 1
def h_WriteFile(e, a, x):
    ent = e.handles.get(a[0])
    if ent and ent[0] == 'file':
        data = e.rd(a[1], a[2])
        _audit('WriteFile', win=ent[2], handle=hex(a[0]), n=a[2], md5=_md5(data), hex=data[:100].hex(' ') if a[2] <= 128 else None)
        if a[2] >= 40: log(f'  [file150] WriteFile handle={a[0]:#x} win={ent[2]!r} src={a[1]:#x} n={a[2]} data={data[:100].hex(" ")}')
        ent[1].write(data); ent[1].flush()
        if a[3]: e.w32(a[3], len(data))
        return 1
    if a[0] in (0xFFFFFFF5, 0xFFFFFFF6, 0xFFFFFFF4):  # std handles -> host log
        log('  [guest write]', e.rd(a[1], a[2])[:200])
        if a[3]: e.w32(a[3], a[2])
        return 1
    e.last_error = 6; return 0
def h_GetFileSize(e, a, x):
    ent = e.handles.get(a[0])
    if not ent or ent[0] != 'file': return 0xFFFFFFFF
    pos = ent[1].tell(); ent[1].seek(0, 2); sz = ent[1].tell(); ent[1].seek(pos)
    if a[1]: e.w32(a[1], 0)
    _audit('GetFileSize', win=ent[2], size=sz)
    return sz
def h_SetFilePointer(e, a, x):
    ent = e.handles.get(a[0])
    if not ent or ent[0] != 'file': return 0xFFFFFFFF
    dist = a[1] - (1 << 32) if a[1] >= (1 << 31) else a[1]
    ent[1].seek(dist, a[3])
    _audit('SetFilePointer', win=ent[2], dist=dist, method=a[3], result=ent[1].tell())
    return ent[1].tell()
def h_CloseHandle(e, a, x):
    ent = e.handles.pop(a[0], None)
    if ent and ent[0] == 'file':
        try: ent[1].close()
        except Exception: pass
    if ent and ent[0] == 'find' and 'fh' in ent[1]:
        pass
    return 1
def h_GetFileAttributesA(e, a, x):
    _p = e.cstr(a[0]); hp = host_path(_p)
    if hp is None or not _os.path.exists(hp):
        _audit('GetFileAttributes', win=_p, host=hp, result='FAIL')
        e.last_error = 2; return 0xFFFFFFFF
    _r = 0x10 if _os.path.isdir(hp) else 0x80
    _audit('GetFileAttributes', win=_p, host=hp, result=hex(_r))
    return _r
def _fill_find(e, addr, hp):
    st = _os.stat(hp)
    e.w32(addr + 0, 0x10 if _os.path.isdir(hp) else 0x80)
    e.w32(addr + 36, 0); e.w32(addr + 40, st.st_size & 0xFFFFFFFF)
    e.put_cstr(addr + 52, _os.path.basename(hp))
    e.put_cstr(addr + 312, '')
def h_FindFirstFileA(e, a, x):
    pat = e.cstr(a[0]); hp = host_path(pat)
    if hp is None:
        _audit('FindFirstFile', win=pat, host=None, result='FAIL-noresolve')
        return 0xFFFFFFFF
    d = _os.path.dirname(hp); base = _os.path.basename(hp)
    try: names = sorted(n for n in _os.listdir(d) if fnmatch.fnmatch(n.lower(), base.lower()))
    except OSError:
        _audit('FindFirstFile', win=pat, host=hp, result='FAIL-listdir')
        return 0xFFFFFFFF
    if not names:
        _audit('FindFirstFile', win=pat, host=hp, dir=d, result='FAIL-nomatch')
        e.last_error = 2; return 0xFFFFFFFF
    h = e.next_handle; e.next_handle += 4
    e.handles[h] = ('find', {'dir': d, 'names': names, 'i': 0})
    _fill_find(e, a[1], _os.path.join(d, names[0]))
    _audit('FindFirstFile', win=pat, host=hp, dir=d, names=names[:8], result=f'handle={h:#x}')
    return h
def h_FindNextFileA(e, a, x):
    ent = e.handles.get(a[0])
    if not ent or ent[0] != 'find': return 0
    st = ent[1]; st['i'] += 1
    if st['i'] >= len(st['names']): e.last_error = 18; return 0
    _fill_find(e, a[1], _os.path.join(st['dir'], st['names'][st['i']]))
    return 1

def h_StringFromGUID2(e, a, x):
    import struct as _sg132
    g = bytes(e.rd(a[0], 16))
    d1, d2, d3 = _sg132.unpack_from('<IHH', g, 0)
    s = '{%08X-%04X-%04X-%02X%02X-%02X%02X%02X%02X%02X%02X}' % (
        d1, d2, d3, g[8], g[9], g[10], g[11], g[12], g[13], g[14], g[15])
    log(f'  [hle] StringFromGUID2 -> {s}')
    if a[1] and a[2] >= len(s) + 1:
        e.wr(a[1], s.encode('utf-16le') + b'\x00\x00')
        return len(s) + 1
    return 0

REG_TREE = {
    'software\\classes\\clsid': {},
    'software\\wow6432node\\sony corporation\\openmg':
        {'Repository': REPO_WIN, 'ContentRootDir': CONTENT_WIN},
    'software\\sony corporation\\openmg':
        {'Repository': REPO_WIN, 'ContentRootDir': CONTENT_WIN},
}

# run152: seed the GENUINE IntegrityCheckID of the Toshiba install that
# minted the .opf (recovered 2026-10-29 from Lola's full registry export,
# HKLM\SOFTWARE\Wow6432Node\Sony Corporation\OpenMG, live-verified by
# Lola on the Toshiba; mixed case exactly as stored). Mechanism ported
# verbatim from the run133/134 seed probes.
for _k in list(REG_TREE.keys()):
    if 'sony corporation' in _k and 'openmg' in _k:
        REG_TREE[_k]['IntegrityCheckID'] = '{B34A50CC-E17B-ce5e-4445-D84F8778899C}'
# run152: seed the GENUINE gBIS dependency TypeLib GUID of the Toshiba
# install: HKLM SOFTWARE Classes Wow6432Node CLSID {69C1DD9E-87E7-40F3-
# 877E-DA23063E8EB8} Dependency, value TypeLib, recovered 2026-10-29
# from Lola's full Toshiba registry export (UTF-16LE; the identical
# entry also sits under Wow6432Node Classes CLSID). On the real
# install the gBIS routine's RegQueryValueExA reads this back and
# IIDFromString parses it into salwrap .data @0x65144f44; the harness
# missed the key, so CoCreateGuid fabricated a constant there and
# that constant (not the genuine GUID) reached maclist invokes #1/#2.
REG_TREE['software\\classes\\clsid\\{69c1dd9e-87e7-40f3-877e-da23063e8eb8}\\dependency'] = {'TypeLib': '{317B92BE-B04A-4EF6-BC04-02346DEFDB20}'}
log('  [seed] gBIS TypeLib seeded: ' + repr('software\\classes\\clsid\\{69c1dd9e-87e7-40f3-877e-da23063e8eb8}\\dependency'))

def _reg_full(hkey, sub):
    roots = {0x80000002: '', 0x80000001: 'hkcu\\', 0x80000000: 'hkcr\\'}
    if hkey in e_reg_handles: base = e_reg_handles[hkey]
    else: base = roots.get(hkey, '')
    return (base + '\\' + sub).strip('\\').lower() if sub else base.lower()
e_reg_handles = {}
def h_RegOpenKeyExA(e, a, x):
    full = _reg_full(a[0], e.cstr(a[1]) if a[1] else '')
    if full in REG_TREE or full == '' or full.startswith('software\\sony corporation') or full.startswith('software\\wow6432node\\sony corporation'):
        h = e.next_hkey; e.next_hkey += 4
        e_reg_handles[h] = full
        if a[4]: e.w32(a[4], h)
        _audit('RegOpenKey', root=hex(a[0]), sub=e.cstr(a[1]) if a[1] else '', full=full, result=0)
        return 0
    if a[4]: e.w32(a[4], 0)
    _audit('RegOpenKey', root=hex(a[0]), sub=e.cstr(a[1]) if a[1] else '', full=full, result=2)
    return 2
def h_RegQueryValueExA(e, a, x):
    full = e_reg_handles.get(a[0], '')
    name = e.cstr(a[1]) if a[1] else ''
    vals = REG_TREE.get(full, {})
    hit = None
    for k, v in vals.items():
        if k.lower() == name.lower(): hit = v
    try: _nw = e.wstr(a[1])[:48] if a[1] else ''
    except Exception: _nw = '<wstr-err>'
    _audit('RegQueryValue', key=full, name=name, name_w=_nw, result=('HIT ' + repr(hit)) if hit is not None else 'MISS')
    if hit is None:
        e.last_error = 2; return 2
    data = hit.encode('latin-1') + b'\0'
    if a[3]: e.w32(a[3], 1)                       # lpType <- REG_SZ (run106 fix: was a[2])
    if a[5]:
        if a[4] == 0:
            e.w32(a[5], len(data))
        elif e.r32(a[5]) < len(data):
            e.w32(a[5], len(data)); return 234
        else:
            e.wr(a[4], data); e.w32(a[5], len(data))
    return 0
def h_RegCloseKey(e, a, x):
    e_reg_handles.pop(a[0], None); return 0
def h_RegCreateKeyExA(e, a, x):
    full = _reg_full(a[0], e.cstr(a[1]) if a[1] else '')
    REG_TREE.setdefault(full, {})
    h = e.next_hkey; e.next_hkey += 4
    e_reg_handles[h] = full
    if a[7]: e.w32(a[7], h)
    if a[8]: e.w32(a[8], 2)
    _audit('RegCreateKey', full=full, result=0)
    return 0
def h_RegSetValueExA(e, a, x):
    full = e_reg_handles.get(a[0], '')
    name = e.cstr(a[1]) if a[1] else '(default)'
    raw = e.rd(a[4], a[5]) if a[4] and a[5] else b''
    _audit('RegSetValue', key=full, name=name, type=a[3], len=a[5], data=raw[:64])
    log(f'  [reg set] {full}\\{name} type={a[3]} len={a[5]} data={raw[:64]!r}')
    REG_TREE.setdefault(full, {})[name] = raw.rstrip(b'\0').decode('latin-1', 'replace')
    return 0

def h_GetSystemDirectoryA(e, a, x):
    s = 'C:\\Windows\\system32'
    if x == 'W':
        b = s.encode('utf-16le')
        if a[1] >= len(s) + 1: e.wr(a[0], b + b'\x00\x00')
        return len(s) if a[1] >= len(s) + 1 else len(s) + 1
    if a[1] >= len(s) + 1: e.put_cstr(a[0], s)
    return len(s) if a[1] >= len(s) + 1 else len(s) + 1
def h_RegFlushKey(e, a, x):
    return 0
def h_RegCreateKeyExW(e, a, x):
    full = _reg_full(a[0], e.wstr(a[1]) if a[1] else '')
    REG_TREE.setdefault(full, {})
    h = e.next_hkey; e.next_hkey += 4
    e_reg_handles[h] = full
    if a[7]: e.w32(a[7], h)
    if a[8]: e.w32(a[8], 2)
    _audit('RegCreateKeyW', full=full, result=0)
    return 0
def h_RegCreateKeyAW(e, a, x):
    sub = (e.wstr(a[1]) if x == 'W' else e.cstr(a[1])) if a[1] else ''
    full = _reg_full(a[0], sub)
    REG_TREE.setdefault(full, {})
    h = e.next_hkey; e.next_hkey += 4
    e_reg_handles[h] = full
    if a[2]: e.w32(a[2], h)
    _audit('RegCreateKeyAW', full=full, result=0)
    return 0
def h_RegOpenKeyW(e, a, x):
    full = _reg_full(a[0], e.wstr(a[1]) if a[1] else '')
    if full in REG_TREE or full == '' or full.startswith('software\\sony corporation') or full.startswith('software\\wow6432node\\sony corporation'):
        h = e.next_hkey; e.next_hkey += 4
        e_reg_handles[h] = full
        if a[2]: e.w32(a[2], h)
        _audit('RegOpenKeyW', full=full, result=0)
        return 0
    if a[2]: e.w32(a[2], 0)
    _audit('RegOpenKeyW', full=full, result=2)
    return 2
def h_GetModuleHandleA(e, a, x):
    if a[0] == 0: return EXE_BASE
    n = e.cstr(a[0]).lower()
    if 'salwrap' in n: return SAL_BASE
    if 'omgutils' in n: return OMG_BASE
    return 0x70000000 + (abs(hash(n)) % 0x1000) * 0x10000
def h_GetModuleHandleW(e, a, x):
    if a[0] == 0: return EXE_BASE
    n = e.wstr(a[0]).lower()
    if 'salwrap' in n: return SAL_BASE
    if 'omgutils' in n: return OMG_BASE
    return 0x70000000 + (abs(hash(n)) % 0x1000) * 0x10000
def h_GetModuleFileNameA(e, a, x):
    p = {SAL_BASE: REPO_WIN + '\\salwrap.dll', OMG_BASE: REPO_WIN + '\\OMGUtils.dll',
         EXE_BASE: 'C:\\salhost.exe'}.get(a[0], 'C:\\Windows\\system32\\kernel32.dll')
    if a[2]: e.wr(a[1], p.encode('latin-1')[:a[2] - 1] + b'\0')
    return min(len(p), a[2] - 1) if a[2] else 0
def h_GetProcAddress(e, a, x):
    if a[1] < 0x10000:
        nm = f'#{a[1]}'
    else:
        nm = e.cstr(a[1])
    spec = HLE.get(nm)
    if spec: return e.make_stub(f'gp!{nm}', f'GetProcAddress:{nm}', spec[0], spec[1], spec[2])
    return e.make_stub(f'gp!{nm}', f'GetProcAddress:{nm}', h_noop0, 'stdcall', 0)
def h_LoadLibraryA(e, a, x):
    return h_GetModuleHandleA(e, a, x)
def h_LoadLibraryW(e, a, x):
    return h_GetModuleHandleW(e, a, x)
def h_GetVersionExA(e, a, x):
    # SESSION 21 FAITHFUL CORRECTION (code evidence in SESSION note):
    # OMGUtils FUN_63919d40 maps GetVersionExA -> OS level (NT: major<5->2,
    # 5->3, >=6->4); salwrap FUN_65103a20 = omgutil(4)!=0 = "OS >= Vista".
    # The target install is Lola's Win7 Toshiba: the real API there
    # answers 6.1.7601 SP1. The old XP SP2 answer (5.1.2600) made gate #1
    # fail in a way the real install never would.
    sz = e.r32(a[0])
    e.w32(a[0] + 4, 6); e.w32(a[0] + 8, 1); e.w32(a[0] + 12, 7601)
    e.w32(a[0] + 16, 2)
    if sz >= 156: e.put_cstr(a[0] + 20, 'Service Pack 1')
    return 1
def h_GetVersion(e, a, x):  return 0x1DB10106
def h_GetSystemInfo(e, a, x):
    e.w32(a[0] + 4, 0x1000); e.w32(a[0] + 8, 0x10000); e.w32(a[0] + 12, 0x7FFEFFFF)
    e.w32(a[0] + 16, 1); e.w32(a[0] + 20, 1); e.w32(a[0] + 24, 586)
    e.w32(a[0] + 32, 0x10000)
    return 0
def h_GetCommandLineA(e, a, x):
    if not hasattr(e, '_cmdline'):
        e._cmdline = e.alloc.alloc(64, 'cmdline'); e.put_cstr(e._cmdline, 'salhost.exe')
    return e._cmdline
def h_HeapAlloc(e, a, x):   return e.alloc.alloc(a[2], 'HeapAlloc')
def h_HeapFree(e, a, x):    e.alloc.free(a[2]); return 1
def h_HeapReAlloc(e, a, x): return e.alloc.realloc(a[2], a[3])
def h_HeapSize(e, a, x):    return e.alloc.size_of(a[2])
def h_GlobalAlloc(e, a, x): return e.alloc.alloc(a[1], 'GlobalAlloc')
def h_GlobalLock(e, a, x):  return a[0]
def h_VirtualAlloc(e, a, x):
    size = (a[1] + 0xFFFF) & ~0xFFFF
    if a[0] and VA_BASE <= a[0] < VA_BASE + VA_SIZE: return a[0]
    got = e.va_next; e.va_next += max(size, 0x10000)
    return got
def h_VirtualQuery(e, a, x):
    e.w32(a[1] + 0, a[0] & ~0xFFF); e.w32(a[1] + 4, VA_BASE)
    e.w32(a[1] + 8, 4); e.w32(a[1] + 12, 0x10000)
    e.w32(a[1] + 16, 0x1000); e.w32(a[1] + 24, 0x20000)
    return 28
def h_InterlockedIncrement(e, a, x):
    v = (e.r32(a[0]) + 1) & 0xFFFFFFFF; e.w32(a[0], v)
    return v - (1 << 32) if v >= (1 << 31) else v
def h_InterlockedDecrement(e, a, x):
    v = (e.r32(a[0]) - 1) & 0xFFFFFFFF; e.w32(a[0], v)
    return v - (1 << 32) if v >= (1 << 31) else v
def h_InterlockedExchange(e, a, x):
    old = e.r32(a[0]); e.w32(a[0], a[1]); return old
def h_InterlockedCompareExchange(e, a, x):
    old = e.r32(a[0])
    if old == a[2]: e.w32(a[0], a[1])
    return old
def h_TlsAlloc(e, a, x):
    i = e.tls_next; e.tls_next += 1; return i
def h_TlsSetValue(e, a, x):
    e.tls_vals[a[0]] = a[1]
    if a[0] < 64: e.w32(AUX_BASE + 0x6000 + a[0] * 4, a[1])
    return 1
def h_TlsGetValue(e, a, x):
    return e.tls_vals.get(a[0], 0)
def h_GetTickCount(e, a, x):
    e.tick += 37; return e.tick
def h_QPC(e, a, x):
    e.tick += 100; e.wr(a[0], struct.pack('<q', e.tick * 100)); return 1
def h_QPF(e, a, x):
    e.wr(a[0], struct.pack('<q', 10_000_000)); return 1
def h_GetLocalTime(e, a, x):
    import time as _t
    _ft = _t.localtime(1793313847)  # run152 FROZEN, aligned with h_time
    e.wr(a[0], struct.pack('<8H', _ft.tm_year, _ft.tm_mon, (_ft.tm_wday + 1) % 7, _ft.tm_mday, _ft.tm_hour, _ft.tm_min, _ft.tm_sec, 0)); return 0
def h_MultiByteToWideChar(e, a, x):
    cp, src, slen, dst, dlen = a[0], a[2], a[3], a[4], a[5]
    if slen == 0xFFFFFFFF: slen = len(e.cstr(src)) + 1
    if cp == 1200:
        s = e.wstr(src, slen // 2)[:slen // 2]
    else:
        s = e.rd(src, slen).decode('latin-1').rstrip('\0') if slen else ''
        if a[3] == 0xFFFFFFFF: s = e.cstr(src)
    need = len(s) + (1 if a[3] == 0xFFFFFFFF else 0)
    if dlen == 0: return need
    e.put_wstr(dst, s)
    return need
def h_WideCharToMultiByte(e, a, x):
    src, slen, dst, dlen = a[2], a[3], a[4], a[5]
    if slen == 0xFFFFFFFF:
        s = e.wstr(src); need = len(s) + 1
    else:
        s = e.wstr(src, slen)[:slen]; need = len(s)
    if dlen == 0: return need
    e.put_cstr(dst, s)
    return need
def h_CreateFileMappingA(e, a, x):
    h = e.next_handle; e.next_handle += 4
    e.handles[h] = ('mapping', a[0]); return h
def h_MapViewOfFile(e, a, x):
    ent = e.handles.get(a[0])
    fsrc = e.handles.get(ent[1]) if ent else None
    size = a[4]
    if fsrc and fsrc[0] == 'file':
        pos = fsrc[1].tell(); fsrc[1].seek(0, 2); total = fsrc[1].tell(); fsrc[1].seek(pos)
        n = size if size else total
        buf = e.alloc.alloc(n, 'MapViewOfFile')
        fsrc[1].seek(a[2]); data = fsrc[1].read(n); fsrc[1].seek(pos)
        if data: e.wr(buf, data)
        return buf
    return e.alloc.alloc(size if size else 0x1000, 'MapViewOfFile anon')
def h_CoCreateInstance(e, a, x):
    log('  [hle] CoCreateInstance called -> class not registered')
    return 0x80040154
def h_SysAllocString(e, a, x):
    s = e.wstr(a[0]) if a[0] else ''
    n = len(s)
    buf = e.alloc.alloc(n * 2 + 6, 'BSTR')
    e.w32(buf, n * 2); e.put_wstr(buf + 4, s)
    return buf + 4
def h_SysFreeString(e, a, x):
    if a[0]: e.alloc.free(a[0] - 4)
    return 0
def h_SysStringLen(e, a, x):
    return e.r32(a[0] - 4) // 2 if a[0] else 0
def h_VariantInit(e, a, x):
    e.wr(a[0], b'\0' * 16); return 0
def h_IIDFromString(e, a, x):
    # ole32 IIDFromString: canonical input is the braced string form;
    # strip optional braces, then the standard GUID struct layout
    # (same packing as h_UuidFromStringW). S_OK on success;
    # CO_E_CLASSSTRING (0x800401F3) on an unparsable string.
    s = e.wstr(a[0]).strip()
    if s.startswith('{') and s.endswith('}'): s = s[1:-1]
    try:
        parts = s.split('-')
        raw = struct.pack('<IHH', int(parts[0], 16), int(parts[1], 16), int(parts[2], 16)) + bytes.fromhex(parts[3] + parts[4])
        e.wr(a[1], raw)
        log(f'  [hle] IIDFromString {s} -> {raw.hex(" ")}')
        return 0
    except Exception:
        return 0x800401F3
def h_UuidFromStringW(e, a, x):
    s = e.wstr(a[0])
    try:
        parts = s.split('-')
        b = bytes.fromhex(parts[0] + parts[1] + parts[2] + parts[3] + parts[4])
        raw = struct.pack('<IHH', int(parts[0], 16), int(parts[1], 16), int(parts[2], 16)) + bytes.fromhex(parts[3] + parts[4])
        e.wr(a[1], raw)
        return 0
    except Exception:
        return 0x6F9
def h_SHGetFolderPathA(e, a, x):
    paths = {0x1A: 'C:\\Users\\Glitched7\\AppData\\Roaming', 0x24: 'C:\\Windows',
             0x25: 'C:\\Windows\\system32', 0x26: 'C:\\Program Files (x86)',
             0x2B: 'C:\\ProgramData', 0x05: 'C:\\Users\\Glitched7\\Documents'}
    p = paths.get(a[1] & 0xFF, 'C:\\ProgramData')
    e.put_cstr(a[4], p); return 0
def h_MessageBoxA(e, a, x):
    log(f'  [guest MessageBox] {e.cstr(a[1])!r} / {e.cstr(a[2])!r}')
    return 1
def h_CreateThread(e, a, x):
    log(f'  [hle] CreateThread start={a[2]:#x} -- NOT run (single-thread harness)')
    h = e.next_handle; e.next_handle += 4
    e.handles[h] = ('thread', None)
    if a[5]: e.w32(a[5], 999)
    return h
def h_GetStdHandle(e, a, x):
    return {0xFFFFFFF6: 0xFFFFFFF6, 0xFFFFFFF5: 0xFFFFFFF5, 0xFFFFFFF4: 0xFFFFFFF4}.get(a[0], 0xFFFFFFF5)

WIN = {
 'CreateFileA': (h_CreateFileA, 'stdcall', 7), 'CreateFileW': (h_CreateFileW, 'stdcall', 7),
 'ReadFile': (h_ReadFile, 'stdcall', 5), 'WriteFile': (h_WriteFile, 'stdcall', 5),
 'GetFileSize': (h_GetFileSize, 'stdcall', 2), 'SetFilePointer': (h_SetFilePointer, 'stdcall', 4),
 'CloseHandle': (h_CloseHandle, 'stdcall', 1), 'GetFileAttributesA': (h_GetFileAttributesA, 'stdcall', 1),
 'GetFileAttributesW': (h_GetFileAttributesA, 'stdcall', 1),
 'FindFirstFileA': (h_FindFirstFileA, 'stdcall', 2), 'FindNextFileA': (h_FindNextFileA, 'stdcall', 2),
 'FindClose': (h_CloseHandle, 'stdcall', 1),
 'RegOpenKeyExA': (h_RegOpenKeyExA, 'stdcall', 5), 'RegOpenKeyA': (h_RegOpenKeyExA, 'stdcall', 3),
 'RegQueryValueExA': (h_RegQueryValueExA, 'stdcall', 6),
 'RegCloseKey': (h_RegCloseKey, 'stdcall', 1),
 'RegCreateKeyExA': (h_RegCreateKeyExA, 'stdcall', 9),
 'RegFlushKey': (h_RegFlushKey, 'stdcall', 1),
 'RegCreateKeyExW': (h_RegCreateKeyExW, 'stdcall', 9),
 'RegCreateKeyA': (h_RegCreateKeyAW, 'stdcall', 3), 'RegCreateKeyW': (h_RegCreateKeyAW, 'stdcall', 3),
 'RegOpenKeyW': (h_RegOpenKeyW, 'stdcall', 3),
 'RegSetValueExA': (h_RegSetValueExA, 'stdcall', 6),
 'RegOpenKeyExW': (h_RegOpenKeyExA, 'stdcall', 5), 'RegQueryValueExW': (h_RegQueryValueExA, 'stdcall', 6),
 'GetModuleHandleA': (h_GetModuleHandleA, 'stdcall', 1), 'GetModuleHandleW': (h_GetModuleHandleW, 'stdcall', 1),
 'GetModuleFileNameA': (h_GetModuleFileNameA, 'stdcall', 3), 'GetModuleFileNameW': (h_GetModuleFileNameA, 'stdcall', 3),
 'GetProcAddress': (h_GetProcAddress, 'stdcall', 2),
 'LoadLibraryA': (h_LoadLibraryA, 'stdcall', 1), 'LoadLibraryW': (h_LoadLibraryW, 'stdcall', 1),
 'LoadLibraryExA': (h_LoadLibraryA, 'stdcall', 3), 'LoadLibraryExW': (h_LoadLibraryW, 'stdcall', 3),
 'FreeLibrary': (h_ret1, 'stdcall', 1),
 'GetVersionExA': (h_GetVersionExA, 'stdcall', 1), 'GetVersionExW': (h_GetVersionExA, 'stdcall', 1),
 'GetVersion': (h_GetVersion, 'stdcall', 0),
 'GetSystemInfo': (h_GetSystemInfo, 'stdcall', 1),
 'GetSystemDirectoryA': (h_GetSystemDirectoryA, 'stdcall', 2), 'GetSystemDirectoryW': (h_GetSystemDirectoryA, 'stdcall', 2),
 'GetCommandLineA': (h_GetCommandLineA, 'stdcall', 0), 'GetCommandLineW': (h_GetCommandLineA, 'stdcall', 0),
 'GetProcessHeap': (lambda e, a, x: 1, 'stdcall', 0),
 'HeapAlloc': (h_HeapAlloc, 'stdcall', 3), 'HeapFree': (h_HeapFree, 'stdcall', 3),
 'HeapReAlloc': (h_HeapReAlloc, 'stdcall', 4), 'HeapSize': (h_HeapSize, 'stdcall', 3),
 'HeapCreate': (lambda e, a, x: 2, 'stdcall', 3), 'HeapDestroy': (h_ret1, 'stdcall', 1),
 'HeapValidate': (h_ret1, 'stdcall', 3),
 'GlobalAlloc': (h_GlobalAlloc, 'stdcall', 2),
 'GlobalFree': (lambda e, a, x: (e.alloc.free(a[0]), a[0])[1] and 0, 'stdcall', 1),
 'GlobalLock': (h_GlobalLock, 'stdcall', 1), 'GlobalUnlock': (h_ret1, 'stdcall', 1),
 'GlobalSize': (lambda e, a, x: e.alloc.size_of(a[0]), 'stdcall', 1),
 'LocalAlloc': (h_GlobalAlloc, 'stdcall', 2),
 'LocalFree': (lambda e, a, x: (e.alloc.free(a[0]), 0)[1], 'stdcall', 1),
 'VirtualAlloc': (h_VirtualAlloc, 'stdcall', 4), 'VirtualFree': (h_ret1, 'stdcall', 3),
 'VirtualQuery': (h_VirtualQuery, 'stdcall', 3), 'VirtualProtect': (h_ret1, 'stdcall', 4),
 'InitializeCriticalSection': (lambda e, a, x: (e.wr(a[0], b'\0' * 24), 0)[1], 'stdcall', 1),
 'InitializeCriticalSectionAndSpinCount': (h_ret1, 'stdcall', 2),
 'EnterCriticalSection': (h_noop0, 'stdcall', 1), 'LeaveCriticalSection': (h_noop0, 'stdcall', 1),
 'DeleteCriticalSection': (h_noop0, 'stdcall', 1), 'TryEnterCriticalSection': (h_ret1, 'stdcall', 1),
 'InterlockedIncrement': (h_InterlockedIncrement, 'stdcall', 1),
 'InterlockedDecrement': (h_InterlockedDecrement, 'stdcall', 1),
 'InterlockedExchange': (h_InterlockedExchange, 'stdcall', 2),
 'InterlockedCompareExchange': (h_InterlockedCompareExchange, 'stdcall', 3),
 'InterlockedExchangeAdd': (lambda e, a, x: (lambda old: (e.w32(a[0], (old + a[1]) & 0xFFFFFFFF), old)[1])(e.r32(a[0])), 'stdcall', 2),
 'TlsAlloc': (h_TlsAlloc, 'stdcall', 0), 'TlsFree': (h_ret1, 'stdcall', 1),
 'TlsSetValue': (h_TlsSetValue, 'stdcall', 2), 'TlsGetValue': (h_TlsGetValue, 'stdcall', 1),
 'GetTickCount': (h_GetTickCount, 'stdcall', 0), 'timeGetTime': (h_GetTickCount, 'stdcall', 0),
 'QueryPerformanceCounter': (h_QPC, 'stdcall', 1), 'QueryPerformanceFrequency': (h_QPF, 'stdcall', 1),
 'GetLocalTime': (h_GetLocalTime, 'stdcall', 1), 'GetSystemTime': (h_GetLocalTime, 'stdcall', 1),
 'MultiByteToWideChar': (h_MultiByteToWideChar, 'stdcall', 6),
 'WideCharToMultiByte': (h_WideCharToMultiByte, 'stdcall', 8),
 'CreateFileMappingA': (h_CreateFileMappingA, 'stdcall', 6), 'CreateFileMappingW': (h_CreateFileMappingA, 'stdcall', 6),
 'MapViewOfFile': (h_MapViewOfFile, 'stdcall', 5), 'UnmapViewOfFile': (h_ret1, 'stdcall', 1),
 'OpenFileMappingA': (lambda e, a, x: 0, 'stdcall', 3),
 'CoInitialize': (h_noop0, 'stdcall', 1), 'CoInitializeEx': (h_noop0, 'stdcall', 2),
 'CoUninitialize': (h_noop0, 'stdcall', 0),
 'CoCreateInstance': (h_CoCreateInstance, 'stdcall', 5),
 'CoTaskMemAlloc': (lambda e, a, x: e.alloc.alloc(a[0], 'CoTaskMem'), 'stdcall', 1),
 'CoTaskMemFree': (h_free, 'stdcall', 1),
 'SysAllocString': (h_SysAllocString, 'stdcall', 1), 'SysFreeString': (h_SysFreeString, 'stdcall', 1),
 'SysStringLen': (h_SysStringLen, 'stdcall', 1),
 'VariantInit': (h_VariantInit, 'stdcall', 1), 'VariantClear': (h_noop0, 'stdcall', 1),
 'UuidFromStringW': (h_UuidFromStringW, 'stdcall', 2), 'UuidFromStringA': (h_UuidFromStringW, 'stdcall', 2),
 'SHGetFolderPathA': (h_SHGetFolderPathA, 'stdcall', 5), 'SHGetFolderPathW': (h_SHGetFolderPathA, 'stdcall', 5),
 'MessageBoxA': (h_MessageBoxA, 'stdcall', 4), 'MessageBoxW': (h_MessageBoxA, 'stdcall', 4),
 'wsprintfA': (h_sprintf, 'cdecl', 2), 'wsprintfW': (h_sprintf, 'cdecl', 2),
 'CreateThread': (h_CreateThread, 'stdcall', 6),
 '_beginthreadex': (h_CreateThread, 'cdecl', 6),
 'GetStdHandle': (h_GetStdHandle, 'stdcall', 1),
 'GetCurrentProcess': (lambda e, a, x: 0xFFFFFFFF, 'stdcall', 0),
 'GetCurrentProcessId': (lambda e, a, x: 4242, 'stdcall', 0),
 'GetCurrentThreadId': (lambda e, a, x: 100, 'stdcall', 0),
 'GetCurrentThread': (lambda e, a, x: 0xFFFFFFFE, 'stdcall', 0),
 'GetLastError': (lambda e, a, x: e.last_error, 'stdcall', 0),
 'SetLastError': (lambda e, a, x: setattr(e, 'last_error', a[0]) or 0, 'stdcall', 1),
 'Sleep': (h_noop0, 'stdcall', 1),
 'WaitForSingleObject': (h_noop0, 'stdcall', 2), 'WaitForMultipleObjects': (h_noop0, 'stdcall', 4),
 'CreateMutexA': (lambda e, a, x: 0x500, 'stdcall', 3), 'CreateMutexW': (lambda e, a, x: 0x500, 'stdcall', 3),
 'CreateEventA': (lambda e, a, x: 0x504, 'stdcall', 4), 'CreateEventW': (lambda e, a, x: 0x504, 'stdcall', 4),
 'SetEvent': (h_ret1, 'stdcall', 1), 'ResetEvent': (h_ret1, 'stdcall', 1),
 'ReleaseMutex': (h_ret1, 'stdcall', 1),
 'IsDebuggerPresent': (h_noop0, 'stdcall', 0),  # run106 REVERTED: 1 makes the engine throw 'Debugger is present' (run90) — the encrypt path refuses debuggers, so this must stay 0; the init int3 is handled via h_except_handler3 instead
 'SetUnhandledExceptionFilter': (h_noop0, 'stdcall', 1),
 'OutputDebugStringA': (lambda e, a, x: log('  [dbg]', e.cstr(a[0])[:200]) or 0, 'stdcall', 1),
 'OutputDebugStringW': (lambda e, a, x: log('  [dbg]', e.wstr(a[0])[:200]) or 0, 'stdcall', 1),
 'GetACP': (lambda e, a, x: 1252, 'stdcall', 0), 'GetOEMCP': (lambda e, a, x: 437, 'stdcall', 0),
 'GetCPInfo': (h_ret1, 'stdcall', 2),
 'GetEnvironmentVariableA': (h_noop0, 'stdcall', 3), 'GetEnvironmentVariableW': (h_noop0, 'stdcall', 3),
 'SetEnvironmentVariableA': (h_ret1, 'stdcall', 2),
 'GetCurrentDirectoryA': (lambda e, a, x: (e.put_cstr(a[1], 'C:\\') if a[0] >= 4 else 4, 3)[1], 'stdcall', 2),
 'SetCurrentDirectoryA': (h_ret1, 'stdcall', 1),
 'WSAStartup': (h_noop0, 'stdcall', 2), 'WSACleanup': (h_noop0, 'stdcall', 0),
 'gethostname': (lambda e, a, x: (e.put_cstr(a[0], 'Glitched7-PC'), 0)[1], 'stdcall', 2),
 'lstrlenA': (h_strlen, 'stdcall', 1), 'lstrlenW': (lambda e, a, x: len(e.wstr(a[0])), 'stdcall', 1),
 'lstrcpyA': (h_strcpy, 'stdcall', 2), 'lstrcatA': (h_strcat, 'stdcall', 2),
 'lstrcmpA': (h_strcmp, 'stdcall', 2), 'lstrcmpiA': (h_stricmp, 'stdcall', 2),
 'IsBadReadPtr': (h_noop0, 'stdcall', 2), 'IsBadWritePtr': (h_noop0, 'stdcall', 2),
 'RaiseException': (h_abort, 'stdcall', 4),
 'TerminateProcess': (h_abort, 'stdcall', 2), 'ExitProcess': (h_abort, 'cdecl', 1),
 'GetStartupInfoA': (lambda e, a, x: (e.wr(a[0], b'\0' * 68), e.w32(a[0], 68), 0)[2], 'stdcall', 1),
 'GetStartupInfoW': (lambda e, a, x: (e.wr(a[0], b'\0' * 68), e.w32(a[0], 68), 0)[2], 'stdcall', 1),
 'FlushFileBuffers': (h_ret1, 'stdcall', 1),
 'SetEndOfFile': (h_ret1, 'stdcall', 1),
 'GetFileType': (lambda e, a, x: 1, 'stdcall', 1),
 'DuplicateHandle': (lambda e, a, x: (e.w32(a[6], a[2]), 1)[1], 'stdcall', 7),
}
HLE.update(WIN)

# ================================================================ runner
def main():
    e = Emu()
    uc = e.uc
    # ---- run152 early: time/rand HLE logging wrappers ----
    _TIMEFNS = {'time', 'clock', 'GetTickCount', 'timeGetTime',
                'QueryPerformanceCounter', 'GetLocalTime', 'GetSystemTime',
                'GetSystemTimeAsFileTime', 'rand', 'srand', 'localtime',
                'gmtime', 'mktime', 'ctime', 'asctime'}
    def _twrap(_nm, _orig):
        def _w(e2, a, x):
            _r = _orig(e2, a, x)
            if getattr(e2, '_tlog', False):
                log(f'  [t150] {_nm} args={[hex(v) for v in a[:3]]} -> {_r!r}')
            return _r
        return _w
    for _tn in list(HLE):
        if _tn in _TIMEFNS:
            _h, _c, _n = HLE[_tn]; HLE[_tn] = (_twrap(_tn, _h), _c, _n)
    e._tlog = True
    # ---- run152 early: slab write-watch [0x107ea000, 0x107ec000) ----
    import unicorn as _ucm150
    _WS = {'on': True, 'lo': 0x107ea000, 'hi': 0x107ec000, 'n': 0, 'logged': 0}
    def _ws_class(_pc):
        if 0x64700000 <= _pc < 0x64732000: return 'PF'
        if 0x65100000 <= _pc < 0x65170000: return 'SAL'
        if 0x63900000 <= _pc < 0x63a00000: return 'OMG'
        if 0x0DEE0000 <= _pc < 0x0DF20000: return 'VMEM'
        if 0x10000000 <= _pc < 0x18000000: return 'HEAP'
        if STUB_BASE <= _pc < STUB_BASE + STUB_SIZE: return 'STUB'
        return '??'
    def _ws_cb(uc_, access, address, size, value, ud):
        if not _WS['on']: return
        if address + size <= _WS['lo'] or address >= _WS['hi']: return
        _WS['n'] += 1
        if _WS['logged'] >= 30000: return
        _WS['logged'] += 1
        try:
            _pc = uc_.reg_read(UC_X86_REG_EIP)
            _esp = uc_.reg_read(UC_X86_REG_ESP)
            _ret = e.r32(_esp)
            log(f"  [ws150] #{_WS['n']} pc={_pc:#x}[{_ws_class(_pc)}] addr={address:#x} size={size} val={value:#x} "
                f"eax={uc_.reg_read(UC_X86_REG_EAX):#x} ecx={uc_.reg_read(UC_X86_REG_ECX):#x} edx={uc_.reg_read(UC_X86_REG_EDX):#x} "
                f"esi={uc_.reg_read(UC_X86_REG_ESI):#x} edi={uc_.reg_read(UC_X86_REG_EDI):#x} [esp]={_ret:#x}")
        except Exception as _ex:
            log(f'  [ws150] log failed: {_ex!r}')
    uc.hook_add(_ucm150.UC_HOOK_MEM_WRITE, _ws_cb)
    log('run152 early instrumentation: time wrappers + slab write-watch [0x107ea000,0x107ec000) ARMED')
    def on_code(uc_, address, size, ud):
        if STUB_BASE <= address < STUB_BASE + STUB_SIZE:
            e.on_stub(address)
    def on_bad(uc_, access, address, size, value, ud):
        # Watchdog: if the same (pc, address) faults over and over, the
        # growth retry is not curing it and emu_start would spin forever
        # inside one instruction (run 33: ~15 min, zero chunks retired,
        # no log lines). Trip to a real fault so the event gets named.
        pc0 = uc_.reg_read(UC_X86_REG_EIP)
        key = (pc0, address, access)
        if getattr(e, '_fault_key', None) == key:
            e._fault_n = getattr(e, '_fault_n', 0) + 1
            if e._fault_n > 2000:
                log(f'  [emu] watchdog: stuck fault pc={pc0:#x} addr={address:#x} '
                    f'access={access} after {e._fault_n} retries')
                e.fault = (access, address, pc0)
                e.stop_reason = f'stuck fault pc={pc0:#x} addr={address:#x}'
                return False
        else:
            e._fault_key = key; e._fault_n = 0
        # Growable stack: the engine probes/commits pages downward from
        # the TEB StackLimit (real Windows grows the stack via its guard
        # page). A touch just below the mapped low edge commits more
        # stack instead of faulting. (Runs 22/23: writes at limit-0x20
        # and limit-0x18, tracking the base wherever it was set.)
        low = getattr(e, 'stack_low', STACK_BASE)
        # Silent guard commits, but only within the host exe's real stack
        # reserve: Omgjbox.exe's PE says SizeOfStackReserve=0x100000,
        # commit=0x1000. The probe walks the whole reserve (run 36 fielded
        # its bottom fault exactly 0x100000 below the limit); a touch
        # below the reserve floor is the dispatchable bottom fault.
        if address < low and address >= STACK_BASE - int(os.environ.get('SAL_RESERVE', '0xFF000'), 0):
            try:
                new_low = address & ~0xFFFF
                p = new_low
                while p < low:                    # 4 KiB pages; the EXE page
                    try:                          # at 0x400000 is skipped,
                        uc_.mem_map(p, 0x1000)    # its neighbours still map
                    except Exception:
                        pass
                    p += 0x1000
                uc_.mem_read(address, 1)          # fault page usable now?
                e.stack_low = new_low
                e.w32(TEB_BASE + 0x08, new_low)   # keep TEB limit honest
                gp = getattr(e, 'grow_pcs', None)
                if gp is None: gp = e.grow_pcs = {}
                pc = uc_.reg_read(UC_X86_REG_EIP)
                gp[pc] = gp.get(pc, 0) + 1
                return True
            except Exception:
                pass                              # not curable: real fault
        pc = uc_.reg_read(UC_X86_REG_EIP)
        e.fault = (access, address, pc)
        e.stop_reason = f'invalid access type={access} addr={address:#x} size={size} pc={pc:#x}'
        log('  [emu]', e.stop_reason)
        return False
    uc.hook_add(UC_HOOK_CODE, on_code, begin=STUB_BASE, end=STUB_BASE + STUB_SIZE - 1)
    uc.hook_add(UC_HOOK_MEM_INVALID, on_bad)
    # ---- run67 shim trace: the patch-shim at 0x65127684 and the
    # generated-code address 0x6516d775 it cycles with during SEH resumes.
    # Logs entry state per hit (cap 500, then hook removed).
    _shim_hits = [0]
    _shim_hooks = []
    def _shim_hook(uc_, address, size, ud):
        _shim_hits[0] += 1
        if _shim_hits[0] > 500:
            for _h in _shim_hooks:
                try: uc_.hook_del(_h)
                except Exception: pass
            return
        from unicorn.x86_const import (UC_X86_REG_EAX as _A, UC_X86_REG_EBP as _B,
                                       UC_X86_REG_ESP as _S)
        def _r32(a):
            try: return e.r32(a)
            except Exception: return None
        def _rb(a):
            try: return e.rd(a, 1)[0] if a else None
            except Exception: return None
        _eax = uc_.reg_read(_A)
        _esp = uc_.reg_read(_S)
        log(f'  [shim67] eip={address:#x} esp={_esp:#x} ebp={uc_.reg_read(_B):#x} '
            f'eax={_eax:#x} [eax]={_rb(_eax)} ret={_r32(_esp)} '
            f'flag={_r32(0x65170a38)} slot={_r32(0x651390cc)}')
        if address == 0x6516d775 and _shim_hits[0] <= 5:
            try: log(f'  [shim67] bytes@0x6516d770: {e.rd(0x6516d770, 32).hex(" ")}')
            except Exception as _ex: log(f'  [shim67] bytes@0x6516d770 unreadable: {_ex}')
    _shim_hooks.append(uc.hook_add(UC_HOOK_CODE, _shim_hook, begin=0x65127680, end=0x651276BF))
    _shim_hooks.append(uc.hook_add(UC_HOOK_CODE, _shim_hook, begin=0x6516D770, end=0x6516D77F))
    e.halt_stub()

    global EXPORTS
    log('loading OMGUtils.dll ...')
    EXPORTS = e.load_pe(_os.path.join(SONY_DIR, 'OMGUtils.dll'), OMG_BASE, True)
    log(f'  {len(EXPORTS)} exports')
    log('loading salwrap.dll ...')
    sal_exports = e.load_pe(_os.path.join(SONY_DIR, 'salwrap.dll'), SAL_BASE, True)
    unresolved = [nm for nm, h, c, n in e.stubs if h is None]
    log(f'stubs: {len(e.stubs)} total, {len(unresolved)} unresolved:')
    for nm in unresolved: log('   ?', nm)

    # Run each DLL's real entry point (DllMainCRTStartup: _initterm static
    # ctors + the DLL's own DllMain) exactly as the Windows loader would.
    import pefile as _pf
    for path, b, nm in ((_os.path.join(SONY_DIR, 'OMGUtils.dll'), OMG_BASE, 'OMGUtils'),
                        (_os.path.join(SONY_DIR, 'salwrap.dll'), SAL_BASE, 'salwrap')):
        ep = b + _pf.PE(path).OPTIONAL_HEADER.AddressOfEntryPoint
        r = e.call(ep, args=(b, 1, 0), label=f'{nm} DllMain')
        log(f'{nm} entry returned {r:#x}; stop={e.stop_reason}')
        e.stop_reason = None
        while INITQ:
            qb, qe = INITQ.pop(0)
            for ptr in range(qb, qe, 4):
                fn = e.r32(ptr)
                if fn:
                    e.call(fn, label=f'{nm} static ctor {fn:#x}')
                    e.stop_reason = None
            log(f'{nm} init table {qb:#x}..{qe:#x} drained')

    # Fallback only: if a static sync object's vtable is still null (its
    # ctor needed something we don't provide), install the no-op fake.
    vt = AUX_BASE + 0x800
    lock = e.make_stub('sync-lock', 'sync.vtbl lock/unlock', h_noop0, 'thiscall', 0)
    for i in range(16): e.w32(vt + 4 * i, lock)
    for g in (SAL_BASE + 0x6B050, OMG_BASE + 0x2DDC8):
        if e.r32(g) == 0:
            e.w32(g, vt); log(f'sync vtable fake installed at {g:#x}')

    # ---- SEH dispatcher (the monkey single-steps under its own handler) ----
    from unicorn.x86_const import (UC_X86_REG_EIP as _EIP, UC_X86_REG_ESP as _ESP,
                                   UC_X86_REG_EFLAGS as _EFLAGS)
    _insn_cnt = [0]
    def _count_cb(uc_, address, size, ud): _insn_cnt[0] += 1
    REC = AUX_BASE + 0x1000; CTX = AUX_BASE + 0x1400; DISP = AUX_BASE + 0x1800
    def seh_dispatch(code, addr, info, feip, fesp):
        e.wr(REC, b'\0' * 0x50)
        e.w32(REC + 0x00, code); e.w32(REC + 0x0C, addr)
        e.w32(REC + 0x10, len(info))
        for i, v in enumerate(info): e.w32(REC + 0x14 + 4 * i, v)
        e.snapshot_ctx(CTX, feip, fesp)
        frame = e.r32(0)                      # SEH chain head (fs:[0] @ TEB 0)
        log(f'  [seh] dispatch entry: code={code:#x} head={frame:#x} '
            f'handler={(e.r32(frame + 4) if frame not in (0, 0xFFFFFFFF) else None)}')
        if code == 0xC0000005:
            _g = lambda o: e.r32(CTX + o)
            log(f'  [seh] snapshot regs: eax={_g(0xB0):#x} ebx={_g(0xA4):#x} '
                f'ecx={_g(0xAC):#x} edx={_g(0xA8):#x} esi={_g(0xA0):#x} '
                f'edi={_g(0x9C):#x} ebp={_g(0xB4):#x} esp={_g(0xC4):#x} '
                f'streamA={[e.r32(_g(0xC4) + 4 * i) for i in range(3)]}')
        # Run78 fallback (single-step only): the probe at 0x6516aa62 reads
        # fs:[0] and overwrites [head+4] with ctxpush, assuming a node
        # exists. When the chain is empty (head==0) that write lands at
        # linear 4 -- exactly what the final run77 fault shows (head=0,
        # [4]=0x65125420). The write is unambiguous evidence of intent:
        # ctxpush was meant to handle the coming #DB. Synthesize a temp
        # node [next=0, handler] so the normal dispatch loop can run it.
        if code == 0x80000004 and frame == 0:
            _h4 = e.r32(4)
            if (SAL_BASE <= _h4 < SAL_BASE + 0x77000 or
                    OMG_BASE <= _h4 < OMG_BASE + 0x33000):
                log(f'  [seh] fallback: empty chain, [4]={_h4:#x}; '
                    f'synthesizing node')
                _tmp = AUX_BASE + 0x1C00
                e.w32(_tmp, 0); e.w32(_tmp + 4, _h4)
                frame = _tmp
        seen = 0
        while frame not in (0, 0xFFFFFFFF) and seen < 32:
            handler = e.r32(frame + 4)
            # The engine's probe cycle reuses the head node's stack slot
            # for its VM context record between faults (the +4 field gets
            # overwritten by resumed-code frames), but the node's handler
            # is a fixed property the engine installed. Remember it from
            # the first successful dispatch at this node and reuse it
            # when the field no longer holds a valid image address.
            cache = getattr(seh_dispatch, '_handlers', None)
            if cache is None: cache = seh_dispatch._handlers = {}
            if (SAL_BASE <= handler < SAL_BASE + 0x77000 or
                    OMG_BASE <= handler < OMG_BASE + 0x33000):
                cache[frame] = handler
            elif frame in cache:
                log(f'  [seh] node {frame:#x}: handler field overwritten; '
                    f'using installed handler {cache[frame]:#x}')
                handler = cache[frame]
                # Experiment (readout #20 addendum 4): cycle 2's streamB
                # carries a return address in slot [1], which only the
                # SPLICE handler consumes; ctxpush replays cycle 1's
                # stale Dr2 target. For the patch function's AV with a
                # dead head node, try the splice handler instead.
                _feip = e.r32(CTX + 0xB8)
                if code == 0xC0000005 and 0x65127680 <= _feip < 0x65127700:
                    log(f'  [seh] experiment: probe AV via splice handler '
                        f'0x65126130 instead of cached ctxpush')
                    handler = 0x65126130
            if handler == 0x65125420:  # ctxpush: log the splice inputs
                _dr2 = e.r32(CTX + 0x0C)
                _esp = e.r32(CTX + 0xC4); _ebp = e.r32(CTX + 0xB4)
                def _rd(a):
                    try: return e.r32(a)
                    except Exception: return None
                _sb0 = _rd(_ebp)
                log(f'  [seh] ctxpush inputs: Dr2={_dr2:#x} -> Eip '
                    f'{_dr2 ^ 0x7FFFFFFF:#x}; streamA@{_esp:#x}: '
                    f'{[_rd(_esp + 4 * i) for i in range(3)]}; '
                    f'streamB@{_ebp:#x}: {[_rd(_ebp + 4 * i) for i in range(2)]}; '
                    f'frame@sb0: [sb0-0x18]={_rd(_sb0 - 0x18) if _sb0 else None} '
                    f'[sb0-4]={_rd(_sb0 - 4) if _sb0 else None}')
            if not (SAL_BASE <= handler < SAL_BASE + 0x77000 or
                    OMG_BASE <= handler < OMG_BASE + 0x33000):
                log(f'  [seh] chain exhausted: bogus handler {handler:#x} '
                    f'at frame {frame:#x} (node repurposed?)')
                try:
                    log(f'  [seh] node bytes {frame:#x}: '
                        f'{e.rd(frame, 48).hex(" ")}')
                    log(f'  [seh] handler bytes: {e.rd(handler, 16).hex(" ")}')
                except Exception:
                    pass
                return None
            log(f'  [seh] try code={code:#x} frame={frame:#x} handler={handler:#x} '
                f'ctxEsp={e.r32(CTX + 0xC4):#x} ctxEbp={e.r32(CTX + 0xB4):#x} '
                f'ctxEip={e.r32(CTX + 0xB8):#x}')
            log(f'  [seh] node pre  {frame:#x}: {e.rd(frame, 16).hex(" ")} '
                f'head={e.r32(0):#x}')
            disp = e.raw_call(handler, [REC, frame, CTX, DISP], label='seh handler')
            log(f'  [seh] node post {frame:#x}: {e.rd(frame, 16).hex(" ")} '
                f'head={e.r32(0):#x}')
            if e.stop_reason:
                log(f'  [seh] handler {handler:#x} faulted: {e.stop_reason}')
                return None
            log(f'  [seh] code={code:#x} frame={frame:#x} handler={handler:#x} -> {disp}')
            if disp == 0: return 0
            if disp == 1:
                frame = e.r32(frame); seen += 1; continue
            return disp
        return None
    # ---- sal_emu157 (Session 20): FH1 C++ catch dispatch ----------------
    # Table-driven from the guest binaries' own FuncInfo / TryBlockMap /
    # UnwindMap data, per the Session-19 spec. No hardcoded throw-site or
    # handler addresses: frame resolution reads the compiler's per-function
    # stub (mov eax, <FuncInfo>; jmp __CxxFrameHandler), matching compares
    # HandlerType.pType against the thrown ThrowInfo's CatchableTypes, and
    # all state changes (catchHigh, the exception-pointer slot, funclet
    # execution) are performed by the same rules __CxxFrameHandler uses.
    def _s32(_v):
        return _v - (1 << 32) if _v >= (1 << 31) else _v
    def _cxx_funcinfo(_stub):
        if STUB_BASE <= _stub < STUB_BASE + STUB_SIZE:
            return None
        try:
            _b = e.rd(_stub, 6)
            if _b[0] != 0xB8 or _b[5] != 0xE9:
                return None
            _fi = struct.unpack('<I', _b[1:5])[0]
            if e.r32(_fi) != 0x19930520:      # FH1 (this binary set)
                return None
            return {'addr': _fi, 'maxState': _s32(e.r32(_fi + 4)),
                    'pUnwindMap': e.r32(_fi + 8), 'nTryBlocks': e.r32(_fi + 0xC),
                    'pTryBlockMap': e.r32(_fi + 0x10)}
        except Exception:
            return None
    def _cxx_run_funclet(_action, _ebp, _tag):
        _halt = e.halt_stub()
        _esp = (_ebp - 0x400) & 0xFFFFFFFF
        try:
            e.w32(_esp, _halt)
        except Exception as _ex:
            log(f'  [cxxeh] funclet {_tag}: stack setup failed: {_ex!r}')
            return False
        uc.reg_write(UC_X86_REG_EBP, _ebp)
        uc.reg_write(UC_X86_REG_ESP, _esp)
        e.stop_reason = None
        try:
            uc.emu_start(_action, _halt, count=2_000_000)
        except UcError as _ex:
            log(f'  [cxxeh] funclet {_tag} @{_action:#x} UcError: {_ex}')
            e.stop_reason = None
            return False
        _eip = uc.reg_read(UC_X86_REG_EIP)
        _ok = _eip == _halt or e.stop_reason == 'halt stub reached'
        log(f'  [cxxeh] funclet {_tag} @{_action:#x} ebp={_ebp:#x} -> eip={_eip:#x} stop={e.stop_reason} ok={_ok}')
        e.stop_reason = None
        return _ok
    def _cxx_unwind_to(_fi, _ebp, _state, _target, _tag):
        _s = _state
        _guard = 0
        while _s > _target and _guard < 64:
            _guard += 1
            if _s < 0 or _s >= _fi['maxState']:
                log(f'  [cxxeh] unwind {_tag}: state {_s} out of range (maxState={_fi["maxState"]})')
                return False
            _ent = _fi['pUnwindMap'] + _s * 8
            _to = _s32(e.r32(_ent)); _act = e.r32(_ent + 4)
            log(f'  [cxxeh] unwind {_tag}: state {_s} -> {_to} action={_act:#x}')
            if _act and not _cxx_run_funclet(_act, _ebp, f'{_tag} s{_s}'):
                return False
            if _to >= _s:
                log(f'  [cxxeh] unwind {_tag}: non-descending toState {_to} from {_s}')
                return False
            _s = _to
        return _s == _target
    def _cxx_transfer(_frames, _tidx, _fi, _tryLow, _catchHigh, _adj, _dispPb,
                      _pHandler, _ctm, _obj, _pend):
        _node, _handler, _state, _ = _frames[_tidx]
        _ebp = (_node + 0xC) & 0xFFFFFFFF
        for _j in range(_tidx):
            _n2, _h2, _s2, _f2 = _frames[_j]
            if _f2:
                if not _cxx_unwind_to(_f2, (_n2 + 0xC) & 0xFFFFFFFF, _s2, -1, f'frame[{_j}]'):
                    log(f'  [cxxeh] unwind of intervening frame[{_j}] failed; dispatch aborted')
                    return None
            else:
                log(f'  [cxxeh] intervening frame[{_j}] node={_n2:#x}: no FH1 tables; popped without funclets')
        if not _cxx_unwind_to(_fi, _ebp, _state, _tryLow, 'target'):
            log('  [cxxeh] target-frame unwind failed; dispatch aborted')
            return None
        _adjobj = (_obj + _ctm['mdisp']) & 0xFFFFFFFF
        if _ctm['pdisp'] >= 0:
            _adjobj = (e.r32((_obj + _ctm['pdisp']) & 0xFFFFFFFF) + _ctm['vdisp']) & 0xFFFFFFFF
        e.w32((_node + 8) & 0xFFFFFFFF, _catchHigh & 0xFFFFFFFF)   # state := catchHigh
        e.w32(0, _node)                                            # fs:[0] := target node
        _slot = (_ebp + _dispPb) & 0xFFFFFFFF
        if _adj & 0x8:                                             # catch by reference
            e.w32(_slot, _adjobj)
            log(f'  [cxxeh] catch-by-reference: slot [{_slot:#x}] := exc ptr {_adjobj:#x}')
        elif _ctm['copyfn']:                                       # catch by value, copy ctor
            _halt = e.halt_stub()
            _esp = (_ebp - 0x400) & 0xFFFFFFFF
            e.w32(_esp, _halt); e.w32(_esp - 4, _adjobj)
            uc.reg_write(UC_X86_REG_ECX, _slot)
            uc.reg_write(UC_X86_REG_EBP, _ebp)
            uc.reg_write(UC_X86_REG_ESP, _esp - 4)
            e.stop_reason = None
            try:
                uc.emu_start(_ctm['copyfn'], _halt, count=1_000_000)
            except UcError as _ex:
                log(f'  [cxxeh] copyfn {_ctm["copyfn"]:#x} UcError: {_ex}')
            log(f'  [cxxeh] catch-by-value: copyfn {_ctm["copyfn"]:#x} constructed at {_slot:#x}')
            e.stop_reason = None
        else:                                                      # catch by value, trivial copy
            e.wr(_slot, e.rd(_adjobj, _ctm['size']))
            log(f'  [cxxeh] catch-by-value: memcpy {_ctm["size"]} B to {_slot:#x}')
        for _r, _v in _pend['regs'].items():
            uc.reg_write(_r, _v)
        uc.reg_write(UC_X86_REG_EBP, _ebp)
        _tesp = (_ebp - 0x400) & 0xFFFFFFFF
        e.w32(_tesp, e.halt_stub())
        uc.reg_write(UC_X86_REG_ESP, _tesp)
        log(f'  [cxxeh] transfer: eip={_pHandler:#x} ebp={_ebp:#x} esp={_tesp:#x} '
            f'state:={_catchHigh} head={_node:#x}')
        return _pHandler
    def _cxx_dispatch(_pend):
        _obj, _ti = _pend['obj'], _pend['ti']
        _thrown = []
        try:
            _cta = e.r32(_ti + 12)
            _n = e.r32(_cta) if _cta else 0
            for _i in range(min(_n, 16)):
                _ct = e.r32(_cta + 4 + 4 * _i)
                _thrown.append({'ct': _ct, 'props': e.r32(_ct), 'td': e.r32(_ct + 4),
                                'mdisp': _s32(e.r32(_ct + 8)), 'pdisp': _s32(e.r32(_ct + 12)),
                                'vdisp': _s32(e.r32(_ct + 16)), 'size': e.r32(_ct + 20),
                                'copyfn': e.r32(_ct + 24)})
        except Exception as _ex:
            log(f'  [cxxeh] ThrowInfo parse failed: {_ex!r}')
            return None
        log(f'  [cxxeh] dispatch: obj={_obj:#x} ti={_ti:#x} ret={_pend["retaddr"]:#x} '
            f'catchables={[(hex(t["td"]), t["mdisp"], t["pdisp"]) for t in _thrown]}')
        _frames = []
        _node = e.r32(0)
        while _node not in (0, 0xFFFFFFFF) and len(_frames) < 32:
            _handler = e.r32(_node + 4)
            _state = _s32(e.r32(_node + 8))
            _fi = _cxx_funcinfo(_handler)
            _frames.append((_node, _handler, _state, _fi))
            _d = len(_frames) - 1
            log(f'  [cxxeh] frame[{_d}] node={_node:#x} handler={_handler:#x} state={_state} '
                f'funcinfo={_fi["addr"]:#x} nTryBlocks={_fi["nTryBlocks"]}' if _fi else
                f'  [cxxeh] frame[{_d}] node={_node:#x} handler={_handler:#x} state={_state} funcinfo=None')
            if _fi:
                for _t in range(_fi['nTryBlocks']):
                    _tb = _fi['pTryBlockMap'] + _t * 0x14
                    _tl, _th, _ch = _s32(e.r32(_tb)), _s32(e.r32(_tb + 4)), _s32(e.r32(_tb + 8))
                    _nc, _ph = e.r32(_tb + 0xC), e.r32(_tb + 0x10)
                    if not (_tl <= _state <= _th):
                        continue
                    for _c in range(_nc):
                        _h = _ph + _c * 0x10
                        _adj, _pt = e.r32(_h), e.r32(_h + 4)
                        _dpb, _phdl = _s32(e.r32(_h + 8)), e.r32(_h + 0xC)
                        _match = None
                        if _pt == 0:
                            _match = _thrown[0] if _thrown else {'mdisp': 0, 'pdisp': -1, 'vdisp': 0, 'size': 0, 'copyfn': 0}
                        else:
                            for _tt in _thrown:
                                if _tt['td'] == _pt:
                                    _match = _tt; break
                        if _match is None:
                            continue
                        log(f'  [cxxeh] MATCH frame[{_d}] node={_node:#x} tryblock[{_t}] '
                            f'[{_tl}..{_th}] catchHigh={_ch} adj={_adj:#x} pType={_pt:#x} '
                            f'dispPb={_dpb} pHandler={_phdl:#x}')
                        return _cxx_transfer(_frames, _d, _fi, _tl, _ch, _adj, _dpb,
                                             _phdl, _match, _obj, _pend)
            _node = e.r32(_node)
        log('  [cxxeh] no handler found; exception escapes (pre-157 end-state)')
        return None
    def _cxx_resume(_begin):
        _halt = e.halt_stub()
        _chunks = 0
        _cur = _begin
        while True:
            try:
                uc.emu_start(_cur, _halt, count=500_000)
            except UcError as _ex:
                if getattr(e, 'fault', None) is None:
                    e.stop_reason = f'UcError {_ex} (cxx resume)'
                break
            _now = uc.reg_read(UC_X86_REG_EIP)
            if _now == _halt or e.stop_reason or getattr(e, 'fault', None):
                break
            _chunks += 1
            if _chunks >= 2000:
                e.stop_reason = 'cxx resume chunk cap reached'
                break
            _cur = _now
        log(f'  [cxxeh] resume from {_begin:#x}: chunks={_chunks} '
            f'eip={uc.reg_read(UC_X86_REG_EIP):#x} stop={e.stop_reason}')
    def run_with_seh(entry, args=(), label='', ecx=None):
        if getattr(e, 'pending_cxx', None) is not None:
            log('  [cxxeh] stale pending throw cleared at phase start')
            e.pending_cxx = None
        r = e.call(entry, args=args, ecx=ecx, label=label)
        rounds = 0
        while True:
            _pend = getattr(e, 'pending_cxx', None)
            if _pend is not None:
                e.pending_cxx = None
                _tgt = _cxx_dispatch(_pend)
                if _tgt is None:
                    e.stop_reason = _pend.get('old_stop') or \
                        "handler error in _CxxThrowException: RuntimeError('guest called abort/exit')"
                    break
                e.stop_reason = None
                _cxx_resume(_tgt)
                continue
            sr = e.stop_reason or ''
            fault = getattr(e, 'fault', None)
            if not (fault or 'EXCEPTION' in sr or 'INSN_INVALID' in sr or 'UcError' in sr):
                break
            feip = uc.reg_read(_EIP); fesp = uc.reg_read(_ESP)
            log(f'  [seh] fault eip={feip:#x} esp={fesp:#x} '
                f'eflags={uc.reg_read(_EFLAGS):#010x} sr={sr[:60]}')
            if fault:
                code, addr = 0xC0000005, fault[2]
                info = [1 if fault[0] in (20, 21) else 0, fault[1]]
            elif 'INSN_INVALID' in sr:
                code, addr, info = 0xC000001D, feip, []
            else:
                try: prev = e.rd(feip - 1, 1)[0]
                except Exception: prev = 0
                if prev == 0xCC: code, addr, info = 0x80000003, feip - 1, []
                else: code, addr, info = 0x80000004, feip, []
            e.fault = None
            # Stack-overflow last-page rule: when a fault at the reserve
            # bottom is delivered, Windows commits that final page (it's
            # what lets an overflow handler run at all). The engine's
            # continuation store targets exactly that page (run 37:
            # 0x6516D775 stored to floor-4 after the bottom splice).
            if code == 0xC0000005 and info:
                fa = info[1]
                low = getattr(e, 'stack_low', STACK_BASE)
                if low - 0x1000 <= fa < low:
                    p = fa & ~0xFFF
                    while p < low:
                        try: uc.mem_map(p, 0x1000)
                        except Exception: pass
                        p += 0x1000
                    e.stack_low = fa & ~0xFFF
                    e.w32(TEB_BASE + 0x08, e.stack_low)
                    log(f'  [seh] bottom-page commit to {e.stack_low:#x}')
            _ring = getattr(e, '_ring', None)
            if _ring:
                _last = list(_ring)[-64:]
                log(f'  [ring86] last {len(_last)} eips before fault: ' +
                    ' '.join(f'{a:#x}' for a in _last))
            if code == 0xC000001D:
                # run84 (read-only): capture the live-patched OMGUtils
                # function1 bytes + the IAT slot + fault-time stack slots.
                try:
                    _ob = e.rd(0x63917800, 0x100)
                    with open('/home/hatch/workspace/atrac-salwrap-work/unicorn/omg-live86.bin', 'wb') as _f:
                        _f.write(_ob)
                    _slot = e.r32(0x639221a4)
                    _stk = [e.r32(fesp + 4 * i) for i in range(6)]
                    log(f'  [live86] omg-dump ok slot[0x639221a4]={_slot:#x} '
                        f'stack@fault-esp={[_s and hex(_s) for _s in _stk]}')
                except Exception as _ex:
                    log(f'  [live86] omg-dump FAILED: {_ex}')
            disp = seh_dispatch(code, addr, info, feip, fesp)
            rounds += 1
            # run83: capture the tail's wild transfer. Hook only the last
            # ~16 rounds (full-run per-insn callback would be far too slow).
            if rounds == 95 and getattr(e, '_ring_hook', None) is None:
                from collections import deque as _dq
                e._ring = _dq(maxlen=256)
                def _ring_cb(uc_, addr, size, _u):
                    e._ring.append(addr)
                e._ring_hook = e.uc.hook_add(UC_HOOK_CODE, _ring_cb)
                log('  [ring86] EIP ring armed at round 95')
            if disp is None:
                log(f'  [seh] UNHANDLED code={code:#x} at {addr:#x}')
                break
            if disp != 0:
                log(f'  [seh] disposition {disp}; stopping')
                break
            log(f'  [seh] edited ctx: ebp={e.r32(CTX + 0xB4):#x} '
                f'esp={e.r32(CTX + 0xC4):#x} eip={e.r32(CTX + 0xB8):#x} '
                f'edi={e.r32(CTX + 0x9C):#x} esi={e.r32(CTX + 0xA0):#x} '
                f'ebx={e.r32(CTX + 0xA4):#x}')
            new_eip = e.apply_ctx(CTX)
            log(f'  [seh] resume regs: eip={new_eip:#x} '
                f'ebp={uc.reg_read(UC_X86_REG_EBP):#x} '
                f'esp={uc.reg_read(UC_X86_REG_ESP):#x} '
                f'code={e.uc.mem_read(new_eip, 8).hex()}')
            # ---- run86 instrumentation (read-only): live .text + frame
            # dump on every 0x65149379 continuation resume. File bytes
            # lie for this region (engine patches its own .text), so
            # only live-memory bytes count.
            if True:  # run82: every resume (stub addr varies per run)
                _n = getattr(e, '_t86', 0); e._t86 = _n + 1
                _ebp = uc.reg_read(UC_X86_REG_EBP)
                _esp = uc.reg_read(UC_X86_REG_ESP)
                def _rd32(a):
                    try: return e.r32(a)
                    except Exception: return None
                try:
                    _tb = e.rd(new_eip - 0x10, 0x100)
                    with open('/home/hatch/workspace/atrac-salwrap-work/unicorn/live-text86-%d.bin' % _n, 'wb') as _f:
                        _f.write(_tb)
                    _tx = _tb.hex(' ')
                except Exception as _ex:
                    _tx = f'DUMP-FAILED: {_ex}'
                if _n == 0:
                    try:
                        _cb = e.rd(0x65125400, 0x200)
                        with open('/home/hatch/workspace/atrac-salwrap-work/unicorn/live-ctxpush86.bin', 'wb') as _f:
                            _f.write(_cb)
                    except Exception:
                        pass
                _fr = ' '.join(
                    f'[ebp{_o:+#x}]={_rd32(_ebp + _o)}'
                    for _o in (-0x20, -0x1c, -0x18, -0x8, -0x4, 0, 4, 8))
                log(f'  [live86] resume#{_n} ebp={_ebp:#x} esp={_esp:#x} '
                    f'ebx={uc.reg_read(UC_X86_REG_EBX):#x} '
                    f'esi={uc.reg_read(UC_X86_REG_ESI):#x} '
                    f'edi={uc.reg_read(UC_X86_REG_EDI):#x} {_fr} '
                    f'text81={_tx}')
            # One trap per trampoline arming: the engine's hop trampolines
            # set TF themselves (pushf/or 0x100/popf) right before each hop.
            # Leaving TF on across a splice-resume makes the CPU re-trap on
            # the very next instruction and the splice handler then consumes
            # a frame that was never a continuation (observed: Ebp=0x10010).
            uc.reg_write(UC_X86_REG_EFLAGS, uc.reg_read(UC_X86_REG_EFLAGS) & ~0x100)
            e.stop_reason = None
            # Chunked resume: emu_start's count is translator-level (fast),
            # unlike a Python code hook. Each exhausted chunk logs a
            # progress line so a long VM grind is distinguishable from a
            # wedge (run 31: 280 s inside one resume, no telemetry).
            halt = e.halt_stub()
            chunks = 0
            begin = new_eip
            while True:
                try:
                    uc.emu_start(begin, halt, count=500_000)
                except UcError as ex:
                    if getattr(e, 'fault', None) is None:
                        e.stop_reason = f'UcError {ex} (resume)'
                    break
                cur = uc.reg_read(_EIP)
                if cur == halt or e.stop_reason or getattr(e, 'fault', None):
                    break
                chunks += 1
                if chunks <= 40 or chunks % 40 == 0:
                    import time as _t
                    log(f'  [seh] resume chunk {chunks}: eip={cur:#x} '
                        f'esp={uc.reg_read(_ESP):#x} hle={len(TRACE)} '
                        f't={_t.strftime("%H:%M:%S")}')
                if chunks >= 2000:
                    e.stop_reason = 'resume chunk cap reached'
                    break
                begin = cur
            log(f'  [seh] resume eip={new_eip:#x} done after {chunks} chunks')
            if rounds % 256 == 0:
                log(f'  [seh] rounds={rounds} eip={new_eip:#x} hle={len(TRACE)}')
            if rounds > 200000:
                log('  [seh] round cap reached'); break
        log(f'{label}: SEH rounds = {rounds}; final stop = {e.stop_reason}')
        return uc.reg_read(UC_X86_REG_EAX)

    # ---- run152 trace setup: bootstrap load path + invoke capture ----
    log('=== run152 trace setup ===')
    import hashlib as _hl
    from unicorn.x86_const import (UC_X86_REG_ECX as _ECX111,
                                   UC_X86_REG_EBP as _EBP111,
                                   UC_X86_REG_EAX as _EAX111)
    _CTXOBJ = [0]
    _SNAPS = []   # (tag, bytes) snapshots of the manager object (0x4d0 B)
    def _snap(_tag):
        try:
            if _CTXOBJ[0]:
                _b = bytes(e.rd(_CTXOBJ[0], 0x4d0))
                _SNAPS.append((_tag, _b))
                log(f'  [snap111] {_tag}: obj={_CTXOBJ[0]:#x} md5={_hl.md5(_b).hexdigest()}')
        except Exception as _ex:
            log(f'  [snap111] {_tag} failed: {_ex!r}')
    def _msstr(_o):
        # MSVC std::string (basic_string): size +0x10, cap +0x14
        try:
            _sz = e.r32(_o + 0x10); _cap = e.r32(_o + 0x14)
            if _sz > 4096: return f'<msstr size={_sz} cap={_cap}>'
            _dp = e.r32(_o) if _cap > 0xf else _o
            return repr(bytes(e.rd(_dp, _sz)))
        except Exception:
            return '<msstr unreadable>'
    def _omgstr(_o):
        # engine OmgString: data +4 (inline if cap<0x10), size +0x14, cap +0x18
        try:
            _sz = e.r32(_o + 0x14); _cap = e.r32(_o + 0x18)
            if _sz > 100000: return f'<omgstr size={_sz} cap={_cap}>'
            _dp = _o + 4 if _cap < 0x10 else e.r32(_o + 4)
            return repr(bytes(e.rd(_dp, min(_sz, 96))))
        except Exception:
            return '<omgstr unreadable>'
    def _fetch111(_e, _path):
        if '.ocm' not in _path.lower():
            return
        log(f'  [fetch111] CreateFile {_path!r}')
        _snap('fetch:' + _path.replace('\\', '/').split('/')[-1])
    _FETCH['cb'] = _fetch111
    def _rd111(_e, _path, _buf, _n):
        if _path and '.ocm' in _path.lower():
            log(f'  [fetch111] ReadFile {_path!r} -> buf={_buf:#x} n={_n}')
    _FETCH['rd'] = _rd111
    _RETQ = {}
    _RECS = {}   # run152: captured bootstrap invoke records by length
    _RETH = set()
    def _ret111_cb(uc_, addr, size, _u):
        _q = _RETQ.get(addr)
        if not _q: return
        _kind, _aux = _q.pop(0)
        try:
            _eax = uc_.reg_read(_EAX111)
            if _kind == 'c840':
                log(f'  [ret111] c840 -> EAX={_eax:#x} outstr={_omgstr(_aux)}')
            elif _kind == 'b160':
                log(f'  [ret111] b160 -> EAX={_eax:#x} out=({e.r32(_aux):#x}, {e.r32(_aux + 4):#x})')
        except Exception as _ex:
            log(f'  [ret111] {_kind} log failed: {_ex!r}')
    def _queue_ret(_ret, _kind, _aux):
        _RETQ.setdefault(_ret, []).append((_kind, _aux))
        if _ret not in _RETH:
            _RETH.add(_ret)
            uc.hook_add(UC_HOOK_CODE, _ret111_cb, begin=_ret, end=_ret + 15)
    _TR111 = {
        0x6511c8a0: 'c8a0-init',
        0x6511d5b0: 'ctx-ctor-d5b0',
        0x65101730: 'str-copy-ctor-01730',
        0x6512c840: 'vminvoke-c840',
        0x65134a10: 'thunk-34a10',
        0x6512c7e0: 'arena-c7e0',
        0x6512c810: 'arena-c810',
        0x6511b160: 'fetch-b160',
    }
    _TRC = {}
    def _tr111(uc_, addr, size, _u):
        _nm = _TR111.get(addr)
        if _nm is None: return
        _c = _TRC.get(addr, 0); _TRC[addr] = _c + 1
        if _c >= 60: return
        try:
            _esp = uc_.reg_read(_ESP); _ecx = uc_.reg_read(_ECX111)
            _ret = e.r32(_esp)
            _a1 = e.r32(_esp + 4); _a2 = e.r32(_esp + 8)
            _a3 = e.r32(_esp + 12); _a4 = e.r32(_esp + 16)
            if addr == 0x6511c8a0:
                _CTXOBJ[0] = _ecx
                log(f'  [tr111] c8a0-init entry: ecx(obj)={_ecx:#x}')
                _snap('c8a0-entry')
            elif addr == 0x6511d5b0:
                log(f'  [tr111] ctx-ctor-d5b0 entry: ecx(obj)={_ecx:#x}')
            elif addr == 0x65101730:
                log(f'  [tr111] 01730 copy-ctor: this={_ecx:#x} src-omg={_omgstr(_a1)}')
            elif addr == 0x6512c840:
                _extra = ''
                try:
                    if 0 < _a3 < 0x10000 and 0x10000 <= _a2 < 0x11000000:
                        _extra = f' spec={bytes(e.rd(_a2, min(_a3, 80)))!r}'
                except Exception: pass
                log(f'  [tr111] vminvoke-c840: vmctx={_a1:#x} p2={_a2:#x} p3={_a3:#x} p4={_a4:#x}{_extra}')
                if _a3 in (0xc, 0x17, 0x1a) and 0x10000 <= _a2 < 0x11000000:
                    try: _RECS[_a3] = bytes(e.rd(_a2, _a3))
                    except Exception: pass
                _queue_ret(_ret, 'c840', _a4)
            elif addr == 0x65134a10:
                log(f'  [tr111] thunk-34a10: a1={_a1:#x} a2={_a2:#x} a3={_a3:#x}')
            elif addr == 0x6511b160:
                log(f'  [tr111] fetch-b160: this={_ecx:#x} out={_a1:#x} name={_omgstr(_a2)}')
                _queue_ret(_ret, 'b160', _a1)
            else:
                log(f'  [tr111] {_nm}: a1={_a1:#x} a2={_a2:#x} a3={_a3:#x} a4={_a4:#x}')
        except Exception as _ex:
            log(f'  [tr111] {_nm} log failed: {_ex!r}')
    for _ta in _TR111:
        uc.hook_add(UC_HOOK_CODE, _tr111, begin=_ta, end=_ta + 15)
    log('run152 trace hooks installed')

    # ---- run152: maclist-invoke instrumentation (Session 11) ----
    import struct as _st129
    _MACN = [0]
    _MACPEND = {}
    _PFTHIS = []
    _OP4REPLY = {'armed': False, 'dumped': False, 'n': 0}
    def _op4_dump_stream(_cell, _arg, _nm, _ret):
        try:
            log(f'  [op4reply] FIRST reader ({_nm}) after op-4 invoke #{_OP4REPLY["n"]} RETURN; caller ret={_ret:#x} cell={_cell:#x} arg={_arg:#x}')
            _cd = bytes(e.rd(_cell, 0x40))
            log(f'  [op4reply] stream cell[0:0x40]: {_hex(_cd)}')
            _sobj = int.from_bytes(_cd[0:4], 'little')
            if 0x10000000 <= _sobj < 0x18000000:
                try:
                    _sd = bytes(e.rd(_sobj, 0x40))
                    log(f'  [op4reply] stream-state obj @{_sobj:#x}[0:0x40]: {_hex(_sd)}')
                    _cur = int.from_bytes(_sd[0x1c:0x20], 'little')
                    if 0x10000000 <= _cur < 0x18000000:
                        log(f'  [op4reply]   reply stream @{_cur:#x}[0:0x100]: {_hex(bytes(e.rd(_cur, 0x100)))}')
                except Exception as _ex: log(f'  [op4reply] stream-state dump failed: {_ex!r}')
            _seen = set()
            for _o in range(0, 0x40, 4):
                _v = int.from_bytes(_cd[_o:_o + 4], 'little')
                if 0x10000000 <= _v < 0x18000000 and _v not in _seen:
                    _seen.add(_v)
                    try: log(f'  [op4reply]   cell+{_o:#04x} -> heap {_v:#x}[0:0x200]: {_hex(bytes(e.rd(_v, 0x200)))}')
                    except Exception as _ex: log(f'  [op4reply]   cell+{_o:#04x} dump failed: {_ex!r}')
            try: log(f'  [op4reply] stack arg-0x20[0:0x60]: {_hex(bytes(e.rd(_arg - 0x20, 0x60)))}')
            except Exception: pass
        except Exception as _ex:
            log(f'  [op4reply] dump failed: {_ex!r}')
    def _parse_stream(_b):
        _f = []; _i = 0
        while _i < len(_b):
            _t = _b[_i]
            if _t == 0x0b:
                _f.append(('END',)); _i += 1; break
            elif _t == 0x01 and _i + 1 < len(_b):
                _v = _b[_i + 1]; _f.append(('int', _v - 256 if _v > 127 else _v)); _i += 2
            elif _t == 0x02 and _i + 2 < len(_b):
                _f.append(('int', int.from_bytes(_b[_i + 1:_i + 3], 'big', signed=True))); _i += 3
            elif _t in (0x03, 0x04) and _i + 1 < len(_b):
                _ln = _b[_i + 1]; _hdr = 2
                if _ln & 0x80:
                    _n = _ln & 0x7f; _ln = int.from_bytes(_b[_i + 2:_i + 2 + _n], 'big'); _hdr = 2 + _n
                _pay = _b[_i + _hdr:_i + _hdr + _ln]
                if _t == 0x04: _f.append(('oct', _pay))
                else: _f.append(('int', int.from_bytes(_pay, 'big', signed=True)))
                _i += _hdr + _ln
            elif _t == 0x05 and _i + 8 < len(_b) + 1:
                _ln, _ptr = _st129.unpack_from('<II', _b, _i + 1)
                _f.append(('ref', _ln, _ptr)); _i += 9
            else:
                _f.append(('byte?', _t)); _i += 1
        return _f
    def _hex(_b):
        return _b.hex(' ') if _b else ''
    def _macret_cb(uc_, addr, size, _u):
        _q = _MACPEND.get(addr)
        if not _q: return
        _ctx129 = _q.pop(0)
        _CB17['win'] = 'native'
        try:
            _eax = uc_.reg_read(_EAX111)
            log(f'  [mac129 #{_ctx129["n"]}] RETURN EAX={_eax:#x}')
            if any(_f[0] == 'int' and _f[1] == 4 for _f in _ctx129.get('fields', ())):
                log(f'  [op4reply] invoke #{_ctx129["n"]} carries the int-4 selector (OP 4): arming full-reply dump')
                _OP4REPLY['armed'] = True; _OP4REPLY['dumped'] = False; _OP4REPLY['n'] = _ctx129['n']
                if 0x10000000 <= _eax < 0x11000000:
                    try: log(f'  [mac129 #{_ctx129["n"]}] EAX arena[0:0x800]: {_hex(bytes(e.rd(_eax, 0x800)))}')
                    except Exception as _ex: log(f'  [op4reply] arena800 failed: {_ex!r}')
            if 0x10000000 <= _eax < 0x11000000:
                try: log(f'  [mac129 #{_ctx129["n"]}] EAX arena[0:0x200]: {_hex(bytes(e.rd(_eax, 0x200)))}')
                except Exception as _ex: log(f'  [mac129] arena dump failed: {_ex!r}')
            for (_ln, _ptr) in _ctx129['refs']:
                try: log(f'  [mac129 #{_ctx129["n"]}] ref AFTER len={_ln} ptr={_ptr:#x}: {_hex(bytes(e.rd(_ptr, min(_ln, 160))))}')
                except Exception: pass
            _a4 = _ctx129['a4']
            try: log(f'  [mac129 #{_ctx129["n"]}] outstr raw @ {_a4:#x}: {_hex(bytes(e.rd(_a4, 0x20)))} omg={_omgstr(_a4)} ms={_msstr(_a4)}')
            except Exception: pass
        except Exception as _ex:
            log(f'  [mac129] ret log failed: {_ex!r}')
    _MACRETH = set()
    def _mac_entry(uc_, addr, size, _u):
        try:
            _esp = uc_.reg_read(_ESP)
            _ret = e.r32(_esp); _a2 = e.r32(_esp + 8); _a3 = e.r32(_esp + 12); _a4 = e.r32(_esp + 16)
            if not (0 < _a3 < 0x10000 and 0x10000 <= _a2 < 0x11000000): return
            _rec = bytes(e.rd(_a2, _a3))
            _fields = _parse_stream(_rec)
            if not any(_f[0] == 'ref' and _f[1] == 33547 for _f in _fields): return
            _MACN[0] += 1; _n = _MACN[0]
            _CB17['win'] = f'mac#{_n}'
            log(f'  [mac129 #{_n}] INVOKE record@{_a2:#x} len={_a3}: {_rec.hex(" ")}')
            _refs = []
            for _f in _fields:
                if _f[0] == 'ref':
                    _refs.append((_f[1], _f[2]))
                    try: log(f'  [mac129 #{_n}]   ref BEFORE len={_f[1]} ptr={_f[2]:#x}: {_hex(bytes(e.rd(_f[2], min(_f[1], 160))))}')
                    except Exception: log(f'  [mac129 #{_n}]   ref BEFORE len={_f[1]} ptr={_f[2]:#x}: <unreadable>')
                elif _f[0] == 'oct':
                    log(f'  [mac129 #{_n}]   oct({len(_f[1])}): {_hex(_f[1])}')
                elif _f[0] == 'int':
                    log(f'  [mac129 #{_n}]   int({_f[1]})')
                else:
                    log(f'  [mac129 #{_n}]   {_f[0]}')
            _MACPEND.setdefault(_ret, []).append({'n': _n, 'refs': _refs, 'a4': _a4, 'fields': _fields})
            if _ret not in _MACRETH:
                _MACRETH.add(_ret)
                uc.hook_add(UC_HOOK_CODE, _macret_cb, begin=_ret, end=_ret + 15)
        except Exception as _ex:
            log(f'  [mac129] entry log failed: {_ex!r}')
    uc.hook_add(UC_HOOK_CODE, _mac_entry, begin=0x6512c840, end=0x6512c840 + 15)
    # ---- run152: FUN_65105170 (op-4 helper) window tagging ----
    _H17RETH = set()
    def _h17_ret(uc_, addr, size, _u):
        if _CB17.get('hdepth', 0): _CB17['hdepth'] -= 1
        log(f'  [cb152] 5170 EXIT (mac#={_MACN[0]})')
    def _h17_entry(uc_, addr, size, _u):
        try:
            _esp = uc_.reg_read(_ESP)
            _ret = e.r32(_esp)
            _args = [e.r32(_esp + 4 + 4 * i) for i in range(4)]
            _ecx = uc_.reg_read(_ECX111)
            from unicorn.x86_const import UC_X86_REG_EDX as _EDX111
            _edx = uc_.reg_read(_EDX111)
            _CB17['hdepth'] = _CB17.get('hdepth', 0) + 1
            log(f'  [cb152] 5170 ENTER stackargs={[hex(v) for v in _args]} ecx={_ecx:#x} edx={_edx:#x} ret={_ret:#x} win={_CB17["win"]} mac#={_MACN[0]}')
            if _ret not in _H17RETH:
                _H17RETH.add(_ret)
                uc.hook_add(UC_HOOK_CODE, _h17_ret, begin=_ret, end=_ret + 15)
        except Exception as _ex:
            log(f'  [cb152] 5170 hook failed: {_ex!r}')
    uc.hook_add(UC_HOOK_CODE, _h17_entry, begin=0x65105170, end=0x65105170 + 15)
    def _dump_pf(_tag):
        if not _PFTHIS: return
        _this = _PFTHIS[-1]
        try:
            _obj = bytes(e.rd(_this, 0x434))
            log(f'  [pf129] {_tag}: ProcessFile this={_this:#x} [0:0x434]:')
            for _o in range(0, 0x434, 32):
                log(f'  [pf129]   +{_o:#05x}: {_hex(_obj[_o:_o + 32])}')
            for _so in (0x20, 0x398, 0x3b4, 0x3d4, 0x3f4, 0x418):
                try: log(f'  [pf129]   str@{_so:#x}: raw={_hex(_obj[_so:_so + 0x1c])} ms={_msstr(_this + _so)}')
                except Exception: pass
        except Exception as _ex:
            log(f'  [pf129] dump failed: {_ex!r}')
    def _icv_entry(uc_, addr, size, _u):
        try:
            _esp = uc_.reg_read(_ESP)
            _code = e.r32(_esp + 4); _p2 = e.r32(_esp + 8); _ret = e.r32(_esp)
            log(f'  [icv129] FUN_65103ee0 status={_code} p2={_p2:#x} ret={_ret:#x}')
            if _code == 2:
                _dump_pf('at MAC throw')
        except Exception as _ex:
            log(f'  [icv129] log failed: {_ex!r}')
    uc.hook_add(UC_HOOK_CODE, _icv_entry, begin=0x65103ee0, end=0x65103ee0 + 15)
    def _helper_entry(uc_, addr, size, _u):
        try:
            _esp = uc_.reg_read(_ESP); _ecx = uc_.reg_read(_ECX111)
            log(f'  [hlp129] helper {addr:#x} entry ecx={_ecx:#x} ret={e.r32(_esp):#x} args={[hex(e.r32(_esp + 4 + 4 * i)) for i in range(4)]}')
        except Exception as _ex:
            log(f'  [hlp129] log failed: {_ex!r}')
    uc.hook_add(UC_HOOK_CODE, _helper_entry, begin=0x65104eb0, end=0x65104eb0 + 15)
    uc.hook_add(UC_HOOK_CODE, _helper_entry, begin=0x65105170, end=0x65105170 + 15)
    # ---- run152: EKB/identity entry watch ----
    _EKBW = {0x6511a4a0: 'FUN_6511a4a0 vt+8 omgid getter', 0x65119b20: 'FUN_65119b20 omgid loader',
             0x65105f40: 'FUN_65105f40 ekbman driver', 0x651065f0: 'FUN_651065f0 newest-ekb loader',
             0x65109c90: 'FUN_65109c90 ekb enum', 0x6510d560: 'FUN_6510d560 GetLocalEKB'}
    _EKBWC = {}
    def _ekbw_entry(uc_, addr, size, _u):
        _EKBWC[addr] = _EKBWC.get(addr, 0) + 1
        if _EKBWC[addr] <= 40:
            try:
                _esp = uc_.reg_read(_ESP)
                log(f'  [ekbw150] ENTER {_EKBW[addr]} count={_EKBWC[addr]} ret={e.r32(_esp):#x}')
            except Exception as _ex:
                log(f'  [ekbw150] log failed: {_ex!r}')
    for _ea in sorted(_EKBW):
        uc.hook_add(UC_HOOK_CODE, _ekbw_entry, begin=_ea, end=_ea + 15)
    log('run152 ekbw hooks armed')
    _RDR129 = {0x651178e0: 'read-buf+84', 0x6511a620: 'read-str+80',
               0x65117700: 'read-byte+8c', 0x65116780: 'read-int+9c'}
    _RDRPEND = {}
    def _rdrret_cb(uc_, addr, size, _u):
        _q = _RDRPEND.get(addr)
        if not _q: return
        _nm, _arg = _q.pop(0)
        try:
            _eax = uc_.reg_read(_EAX111)
            _extra = ''
            if _nm == 'read-buf+84':
                _ptr = e.r32(_arg); _ln = e.r32(_arg + 4)
                _extra = f' desc=({_ptr:#x},{_ln})'
                if 0 < _ln <= 0x1000 and 0x10000 <= _ptr < 0x11000000:
                    _extra += f' data={_hex(bytes(e.rd(_ptr, min(_ln, 96))))}'
            elif _nm == 'read-str+80':
                _extra = f' str={_omgstr(_arg)} raw={_hex(bytes(e.rd(_arg, 0x1c)))}'
            elif _nm in ('read-byte+8c', 'read-int+9c'):
                try: _extra = f' out32={e.r32(_arg):#x}'
                except Exception: pass
            log(f'  [rdr129] {_nm} -> EAX={_eax:#x}{_extra}')
        except Exception as _ex:
            log(f'  [rdr129] ret log failed: {_ex!r}')
    _RDRRETH = set()
    def _rdr_entry(uc_, addr, size, _u):
        _nm = _RDR129.get(addr)
        if _nm is None: return
        try:
            _esp = uc_.reg_read(_ESP); _ret = e.r32(_esp)
            if not ((0x65104eb0 <= _ret < 0x65105170) or (0x65105170 <= _ret < 0x65105900)): return
            _cell = e.r32(_esp + 4); _arg = e.r32(_esp + 8)
            log(f'  [rdr129] {_nm} called from helper ret={_ret:#x} cell={_cell:#x} arg={_arg:#x}')
            if _OP4REPLY['armed'] and not _OP4REPLY['dumped'] and 0x65105170 <= _ret < 0x65105900:
                _OP4REPLY['dumped'] = True
                _op4_dump_stream(_cell, _arg, _nm, _ret)
            _RDRPEND.setdefault(_ret, []).append((_nm, _arg))
            if _ret not in _RDRRETH:
                _RDRRETH.add(_ret)
                uc.hook_add(UC_HOOK_CODE, _rdrret_cb, begin=_ret, end=_ret + 15)
        except Exception as _ex:
            log(f'  [rdr129] entry log failed: {_ex!r}')
    for _ra in _RDR129:
        uc.hook_add(UC_HOOK_CODE, _rdr_entry, begin=_ra, end=_ra + 15)
    def _pfctor_entry(uc_, addr, size, _u):
        try:
            _esp = uc_.reg_read(_ESP); _ecx = uc_.reg_read(_ECX111)
            _PFTHIS.append(_ecx)
            log(f'  [pf129] ProcessFile ctor FUN_647180a2 entry this={_ecx:#x} ret={e.r32(_esp):#x} args={[hex(e.r32(_esp + 4 + 4 * i)) for i in range(3)]}')
        except Exception as _ex:
            log(f'  [pf129] ctor log failed: {_ex!r}')
    uc.hook_add(UC_HOOK_CODE, _pfctor_entry, begin=0x647180a2, end=0x647180a2 + 15)
    log('run152 maclist instrumentation installed')

    # ---- Session 19 (run156): DB-state singleton / seed-core observational hooks ----
    from unicorn import UC_HOOK_MEM_WRITE as _S19_HOOK_MEM_WRITE
    _S19 = {'obj': 0, 'dumped': set()}
    def _s19_mod(_a):
        if 0x65100000 <= _a < 0x65170000: return 'salwrap'
        if 0x64700000 <= _a < 0x64732000: return 'pfcom'
        if 0x63900000 <= _a < 0x63a00000: return 'OMGUtils'
        return '..'
    def _s19_fields(_o):
        try:
            return (f'+0={e.r32(_o):#x} +0xbc={e.r32(_o + 0xbc):#x} '
                    f'+0x94={e.r32(_o + 0x94):#x} +0xb8={e.rd(_o + 0xb8, 1)[0]:#x}')
        except Exception as _ex:
            return f'fields unreadable: {_ex!r}'
    def _s19_stdstr(_o, _off):
        try:
            _sz = e.r32(_o + _off + 0x10); _cap = e.r32(_o + _off + 0x14)
            if _sz > 4096: return f'<bad size {_sz}>'
            _dp = _o + _off if _cap < 0x10 else e.r32(_o + _off)
            return repr(bytes(e.rd(_dp, _sz)))
        except Exception as _ex:
            return f'<err {_ex!r}>'
    def _s19_omgstr(_o, _off):
        try:
            _sz = e.r32(_o + _off + 0x14); _cap = e.r32(_o + _off + 0x18)
            if _sz > 4096: return f'<bad size {_sz}>'
            _dp = _o + _off + 4 if _cap < 0x10 else e.r32(_o + _off + 4)
            return repr(bytes(e.rd(_dp, _sz)))
        except Exception as _ex:
            return f'<err {_ex!r}>'
    def _s19_watch_cb(uc_, access, address, size, value, ud):
        _o = _S19['obj']
        if not _o: return
        for _tgt, _nm in ((_o, '+0'), (_o + 0xbc, '+0xbc')):
            if address <= _tgt < address + size:
                try:
                    _pc = uc_.reg_read(UC_X86_REG_EIP)
                    log(f'  [s19] WRITE singleton{_nm} size={size} val={value:#x} pc={_pc:#x}({_s19_mod(_pc)})')
                except Exception:
                    pass
    uc.hook_add(_S19_HOOK_MEM_WRITE, _s19_watch_cb)
    def _s19_entry(_name):
        def _cb(uc_, addr, size, _u):
            try:
                _esp = uc_.reg_read(UC_X86_REG_ESP); _ecx = uc_.reg_read(UC_X86_REG_ECX)
                _ret = e.r32(_esp)
                if _name == 'getter6510cd50':
                    _s = e.r32(0x65144f20)
                    if _s and not _S19['obj']: _S19['obj'] = _s
                    log(f'  [s19] getter FUN_6510cd50 entry: singleton={_s:#x}' + (f' ({_s19_fields(_s)})' if _s else '') + f' ret={_ret:#x}({_s19_mod(_ret)})')
                elif _name == 'ctor65104900':
                    _S19['obj'] = _ecx
                    log(f'  [s19] singleton ctor FUN_65104900 entry: obj={_ecx:#x} ret={_ret:#x}({_s19_mod(_ret)})')
                elif _name == 'ca30':
                    log(f'  [s19] ensure-init FUN_6510ca30 entry: this={_ecx:#x} {_s19_fields(_ecx)} ret={_ret:#x}({_s19_mod(_ret)})')
                elif _name == 'openCore65103dc0':
                    log(f'  [s19] openCore FUN_65103dc0 entry: this={_ecx:#x} *this={e.r32(_ecx):#x} outptr={e.r32(_esp + 4):#x} ret={_ret:#x}({_s19_mod(_ret)})')
                elif _name == 'closeCore651048d0':
                    log(f'  [s19] closeCore FUN_651048d0 entry: this={_ecx:#x} *this={e.r32(_ecx):#x} ret={_ret:#x}({_s19_mod(_ret)})')
                elif _name in ('wrap651099c0', 'wrap65109b90'):
                    log(f'  [s19] {_name} entry: this={_ecx:#x} {_s19_fields(_ecx)} ret={_ret:#x}({_s19_mod(_ret)}) args=({e.r32(_esp + 4):#x}, {e.r32(_esp + 8):#x})')
                elif _name == 'load65109380':
                    log(f'  [s19] FUN_65109380 entry: this={_ecx:#x} {_s19_fields(_ecx)} ret={_ret:#x}({_s19_mod(_ret)}) outstr={e.r32(_esp + 4):#x}')
                    if _ecx not in _S19['dumped']:
                        _S19['dumped'].add(_ecx)
                        _raw = bytes(e.rd(_ecx, 0x130))
                        log(f'  [s19] DB-STATE OBJECT @{_ecx:#x} [0:0x130]: {_raw.hex(" ")}')
                        log(f'  [s19]   lockvtable(+4)={e.r32(_ecx + 4):#x} name(+0x10)={_s19_stdstr(_ecx, 0x10)} files: {_s19_stdstr(_ecx, 0x30)} | {_s19_stdstr(_ecx, 0x4c)} | {_s19_stdstr(_ecx, 0x68)} omgstr(+0x80)={_s19_omgstr(_ecx, 0x80)} omgstr(+0x9c)={_s19_omgstr(_ecx, 0x9c)} omgstr(+0x100)={_s19_omgstr(_ecx, 0x100)} kdrm_mmap(+0x11c)={e.r32(_ecx + 0x11c):#x} kdrm_val(+0x120)={e.r32(_ecx + 0x120):#x}')
                elif _name == 'guard65103e50':
                    log(f'  [s19] guard FUN_65103e50 entry: obj={_ecx:#x} *obj={e.r32(_ecx):#x} ret={_ret:#x}({_s19_mod(_ret)})')
                elif _name == 'seedchk65116210':
                    _p = e.r32(_esp + 4)
                    log(f'  [s19] FUN_65116210 seed-check entry: seedptr={_p:#x} bytes={bytes(e.rd(_p, 20)).hex(" ")} ret={_ret:#x}({_s19_mod(_ret)})')
            except Exception as _ex:
                log(f'  [s19] {_name} hook failed: {_ex!r}')
        return _cb
    for _nm, _ea in (('getter6510cd50', 0x6510cd50), ('ctor65104900', 0x65104900),
                     ('ca30', 0x6510ca30), ('openCore65103dc0', 0x65103dc0),
                     ('closeCore651048d0', 0x651048d0), ('wrap651099c0', 0x651099c0),
                     ('wrap65109b90', 0x65109b90), ('load65109380', 0x65109380),
                     ('guard65103e50', 0x65103e50), ('seedchk65116210', 0x65116210)):
        uc.hook_add(UC_HOOK_CODE, _s19_entry(_nm), begin=_ea, end=_ea + 15)
    def _s19_after_open(uc_, addr, size, _u):
        try:
            _edi = uc_.reg_read(UC_X86_REG_EDI); _ebp = uc_.reg_read(UC_X86_REG_EBP)
            _fa = e.rd(_ebp - 0x4f, 1)[0]
            log(f'  [s19] ca30 after openCore: this={_edi:#x} *this={e.r32(_edi):#x} flagA={_fa:#x}')
        except Exception as _ex:
            log(f'  [s19] after-open hook failed: {_ex!r}')
    uc.hook_add(UC_HOOK_CODE, _s19_after_open, begin=0x6510cb92, end=0x6510cb92 + 15)
    def _s19_after_chk(uc_, addr, size, _u):
        try:
            log(f'  [s19] ca30 after FUN_65116210: verdict EAX={uc_.reg_read(UC_X86_REG_EAX):#x}')
        except Exception as _ex:
            log(f'  [s19] after-chk hook failed: {_ex!r}')
    uc.hook_add(UC_HOOK_CODE, _s19_after_chk, begin=0x6510cbae, end=0x6510cbae + 15)
    log('run156 s19 instrumentation installed')

    _S21_ON = False   # bisect variant: s21 hooks disabled
    if _S21_ON:
        # ================= SESSION 21 instrumentation (OBSERVATIONAL ONLY) ====
        # Gates (65103a20 omgutil(4), 65114d50 registry predicate family),
        # 8ea0 entry/branches, 8330 entry/return + extracted strings, 161b0.
        # No guest state is written by any of these hooks.
        _S21 = {'pend': {}}
        _S21_RETH = set()
        def _s21_push(_tag, _fr):
            _S21['pend'].setdefault(_tag, []).append(_fr)
        def _s21_pop(_tag, _retaddr):
            _lst = _S21['pend'].get(_tag) or []
            for _i in range(len(_lst) - 1, -1, -1):
                if _lst[_i].get('ret') == _retaddr:
                    return _lst.pop(_i)
            return _lst.pop() if _lst else None
        def _s21_arm_ret(_tag, _retaddr, _fmt):
            if (_tag, _retaddr) in _S21_RETH: return
            _S21_RETH.add((_tag, _retaddr))
            def _cb(uc_, addr, size, _u, _tag=_tag, _fmt=_fmt):
                _fr = _s21_pop(_tag, addr)
                if _fr is None: return
                try: _fmt(uc_, _fr)
                except Exception as _ex: log(f'  [s21] {_tag} ret-hook failed: {_ex!r}')
            uc.hook_add(UC_HOOK_CODE, _cb, begin=_retaddr, end=_retaddr + 15)
        def _s21_str(_p, _max=80):
            # dump one string object: raw fields + OMG/MSVC71 layout reading
            # (data@+4 or [+4], size@+0x14, cap@+0x18)
            if not _p: return 'NULL'
            try:
                _sz = e.r32(_p + 0x14); _cap = e.r32(_p + 0x18)
                _dp = e.r32(_p + 4) if _cap >= 0x10 else _p + 4
                _b = bytes(e.rd(_dp, min(_sz, _max))) if _sz < 0x100000 else b'<badsize>'
                return f'@{_p:#x} size={_sz} cap={_cap} data={_b!r}'
            except Exception as _ex:
                return f'@{_p:#x} <err {_ex!r}>'
        # -- ca30 attempt scope: clear stale frames; log ca30 exits --
        def _s21_ca30_scope(uc_, addr, size, _u):
            _S21['pend'] = {}
        uc.hook_add(UC_HOOK_CODE, _s21_ca30_scope, begin=0x6510ca30, end=0x6510ca30 + 15)
        def _s21_ca30_exit(_tag):
            def _cb(uc_, addr, size, _u):
                log(f'  [s21] ca30 -> {_tag}')
            return _cb
        uc.hook_add(UC_HOOK_CODE, _s21_ca30_exit('RESTORE BLOCK (cc5c)'), begin=0x6510cc5c, end=0x6510cc5c + 15)
        uc.hook_add(UC_HOOK_CODE, _s21_ca30_exit('DONE (ccc9)'), begin=0x6510ccc9, end=0x6510ccc9 + 15)
        # -- FUN_65103a20 (omgutil(4)!=0) + OMGUtils level FUN_63919d40 --
        def _s21_e_3a20(uc_, addr, size, _u):
            _esp = uc_.reg_read(UC_X86_REG_ESP)
            _s21_push('a20', {'ret': e.r32(_esp)})
            _s21_arm_ret('a20', e.r32(_esp), lambda u2, fr: log(f'  [s21] FUN_65103a20 omgutil(4)!=0 -> EAX={u2.reg_read(UC_X86_REG_EAX):#x}'))
        uc.hook_add(UC_HOOK_CODE, _s21_e_3a20, begin=0x65103a20, end=0x65103a20 + 15)
        def _s21_e_level(uc_, addr, size, _u):
            _esp = uc_.reg_read(UC_X86_REG_ESP)
            _s21_push('lvl', {'ret': e.r32(_esp)})
            _s21_arm_ret('lvl', e.r32(_esp), lambda u2, fr: log(f'  [s21] OMGUtils FUN_63919d40 OS level -> EAX={u2.reg_read(UC_X86_REG_EAX):#x} (1=9x 2=NT<5 3=5.x 4=>=6)'))
        uc.hook_add(UC_HOOK_CODE, _s21_e_level, begin=0x63919d40, end=0x63919d40 + 15)
        def _s21_e_omgutil(uc_, addr, size, _u):
            _esp = uc_.reg_read(UC_X86_REG_ESP)
            log(f'  [s21] omgutil(selector={e.r32(_esp + 4):#x}) entry ret={e.r32(_esp):#x}')
        uc.hook_add(UC_HOOK_CODE, _s21_e_omgutil, begin=0x6391a2e0, end=0x6391a2e0 + 15)
        # -- FUN_65114d50 + family --
        def _s21_e_14d50(uc_, addr, size, _u):
            _esp = uc_.reg_read(UC_X86_REG_ESP)
            _s21_push('d50', {'ret': e.r32(_esp), 'ecx': uc_.reg_read(UC_X86_REG_ECX), 'trace0': len(TRACE)})
            _s21_arm_ret('d50', e.r32(_esp), lambda u2, fr: log(f'  [s21] FUN_65114d50 (registry predicate) -> EAX={u2.reg_read(UC_X86_REG_EAX):#x} (TRACE window {fr["trace0"]}..{len(TRACE)})'))
            log(f'  [s21] FUN_65114d50 entry: desc(ecx)={uc_.reg_read(UC_X86_REG_ECX):#x} TRACE0={len(TRACE)}')
        uc.hook_add(UC_HOOK_CODE, _s21_e_14d50, begin=0x65114d50, end=0x65114d50 + 15)
        def _s21_desc_dump(uc_, addr, size, _u):
            # at 0x65114d76 ECX = &descriptor, 118d0 has filled the fields
            try:
                _d = uc_.reg_read(UC_X86_REG_ECX)
                _fld = []
                for _off in range(0x1b0, 0x1ec, 4):
                    _sp = e.r32(_d + _off)
                    _fld.append(f'+{_off:#x}={e.cstr(_sp) if _sp else None!r}')
                log(f'  [s21] 118d0 descriptor @{_d:#x}: ' + ' '.join(_fld))
            except Exception as _ex:
                log(f'  [s21] desc dump failed: {_ex!r}')
        uc.hook_add(UC_HOOK_CODE, _s21_desc_dump, begin=0x65114d76, end=0x65114d76 + 15)
        for _gt, _ga in (('14a20', 0x65114a20), ('14c20', 0x65114c20), ('12260', 0x65112260)):
            def _mk(_t, _a):
                def _e(uc_, addr, size, _u):
                    _esp = uc_.reg_read(UC_X86_REG_ESP)
                    _s21_push(_t, {'ret': e.r32(_esp)})
                    _s21_arm_ret(_t, e.r32(_esp), lambda u2, fr, _t=_t: log(f'  [s21] FUN_651{_t} -> EAX={u2.reg_read(UC_X86_REG_EAX):#x}'))
                return _e
            uc.hook_add(UC_HOOK_CODE, _mk(_gt, _ga), begin=_ga, end=_ga + 15)
        # -- FUN_65103bd0 (gate registry-query helper): name + result --
        def _s21_e_3bd0(uc_, addr, size, _u):
            _esp = uc_.reg_read(UC_X86_REG_ESP)
            try: _nm = e.cstr(e.r32(_esp + 8))
            except Exception: _nm = '?'
            _s21_push('bd0', {'ret': e.r32(_esp), 'name': _nm, 'key': e.r32(_esp + 4)})
            _s21_arm_ret('bd0', e.r32(_esp), lambda u2, fr: log(f'  [s21] FUN_65103bd0(key={fr["key"]:#x}, name={fr["name"]!r}) -> EAX={u2.reg_read(UC_X86_REG_EAX):#x}'))
        uc.hook_add(UC_HOOK_CODE, _s21_e_3bd0, begin=0x65103bd0, end=0x65103bd0 + 15)
        # -- ca30 gate outcome PCs --
        def _s21_gate_armed(uc_, addr, size, _u):
            log('  [s21] ca30 gates BOTH PASSED -> out-pointer = &[ebp-0x4e] (armed)')
        uc.hook_add(UC_HOOK_CODE, _s21_gate_armed, begin=0x6510cbdc, end=0x6510cbdc + 15)
        def _s21_gate_call(uc_, addr, size, _u):
            _esp = uc_.reg_read(UC_X86_REG_ESP)
            log(f'  [s21] ca30 calls 8ea0 with out-ptr = {e.r32(_esp):#x}')
        uc.hook_add(UC_HOOK_CODE, _s21_gate_call, begin=0x6510cbe5, end=0x6510cbe5 + 15)
        # -- FUN_65108ea0 entry/return + branch PCs --
        def _s21_e_ea0(uc_, addr, size, _u):
            _esp = uc_.reg_read(UC_X86_REG_ESP); _ecx = uc_.reg_read(UC_X86_REG_ECX)
            _out = e.r32(_esp + 4)
            _s21_push('ea0', {'ret': e.r32(_esp), 'out': _out})
            _s21_arm_ret('ea0', e.r32(_esp), lambda u2, fr: log(f'  [s21] FUN_65108ea0 -> AL={u2.reg_read(UC_X86_REG_EAX) & 0xff:#x} *out(final)={(e.rd(fr["out"], 1)[0] if fr["out"] else None)}'))
            log(f'  [s21] FUN_65108ea0 entry: this={_ecx:#x} out={_out:#x} *out@entry={(e.rd(_out, 1)[0] if _out else None)} ret={e.r32(_esp):#x}')
        uc.hook_add(UC_HOOK_CODE, _s21_e_ea0, begin=0x65108ea0, end=0x65108ea0 + 15)
        def _s21_gfa(uc_, addr, size, _u):
            _esi = uc_.reg_read(UC_X86_REG_ESI); _eax = uc_.reg_read(UC_X86_REG_EAX)
            try: _nm = e.cstr(_esi)
            except Exception: _nm = '?'
            log(f'  [s21] 8ea0 GetFileAttributesA({_nm!r}) = {_eax:#x}')
        uc.hook_add(UC_HOOK_CODE, _s21_gfa, begin=0x65108f50, end=0x65108f50 + 15)
        def _s21_pc(_msg):
            def _cb(uc_, addr, size, _u): log(f'  [s21] 8ea0: {_msg}')
            return _cb
        uc.hook_add(UC_HOOK_CODE, _s21_pc('8330 SUCCESS branch (90cc)'), begin=0x651090cc, end=0x651090cc + 15)
        uc.hook_add(UC_HOOK_CODE, _s21_pc('SUB-PATH entry (91cf)'), begin=0x651091cf, end=0x651091cf + 15)
        uc.hook_add(UC_HOOK_CODE, _s21_pc('8330 returned FAILURE -> next file (8ffe)'), begin=0x65108ffe, end=0x65108ffe + 15)
        def _s21_planted(uc_, addr, size, _u):
            _eax = uc_.reg_read(UC_X86_REG_EAX)
            try: _b = bytes(e.rd(_eax, 20)).hex(' ')
            except Exception: _b = '?'
            log(f'  [s21] 8ea0 DIRECT PATH: 20B seed copied into mapping @{_eax:#x}: {_b} (161b0 next)')
        uc.hook_add(UC_HOOK_CODE, _s21_planted, begin=0x65109124, end=0x65109124 + 15)
        # -- FUN_65108330 entry/return + extracted strings --
        def _s21_e_8330(uc_, addr, size, _u):
            _esp = uc_.reg_read(UC_X86_REG_ESP); _ecx = uc_.reg_read(UC_X86_REG_ECX)
            _fr = {'ret': e.r32(_esp), 'a1': e.r32(_esp + 4), 'a2': e.r32(_esp + 8),
                   'a3': e.r32(_esp + 0xc), 'a4': e.r32(_esp + 0x10)}
            _s21_push('p30', _fr)
            def _fmt(u2, fr):
                log(f'  [s21] FUN_65108330 -> AL={u2.reg_read(UC_X86_REG_EAX) & 0xff:#x} EAX={u2.reg_read(UC_X86_REG_EAX):#x}')
                log(f'  [s21]   arg1 CONTENT : {_s21_str(fr["a1"])}')
                log(f'  [s21]   arg2 S0/name : {_s21_str(fr["a2"])}')
                log(f'  [s21]   arg3 SUB     : {_s21_str(fr["a3"])}')
                log(f'  [s21]   arg4 SEED    : {_s21_str(fr["a4"])}')
            _s21_arm_ret('p30', _fr['ret'], _fmt)
            log(f'  [s21] FUN_65108330 entry: this={_ecx:#x} a1={_fr["a1"]:#x} a2={_fr["a2"]:#x} a3={_fr["a3"]:#x} a4(SEED-out)={_fr["a4"]:#x}')
        uc.hook_add(UC_HOOK_CODE, _s21_e_8330, begin=0x65108330, end=0x65108330 + 15)
        # -- FUN_651161b0 (direct-path seed validate) --
        def _s21_e_161b0(uc_, addr, size, _u):
            _esp = uc_.reg_read(UC_X86_REG_ESP)
            _p = e.r32(_esp + 4)
            try: _b = bytes(e.rd(_p, 20)).hex(' ')
            except Exception: _b = '?'
            _s21_push('61b0', {'ret': e.r32(_esp)})
            _s21_arm_ret('61b0', e.r32(_esp), lambda u2, fr: log(f'  [s21] FUN_651161b0 -> EAX={u2.reg_read(UC_X86_REG_EAX):#x}'))
            log(f'  [s21] FUN_651161b0 entry: seed@{_p:#x}: {_b}')
        uc.hook_add(UC_HOOK_CODE, _s21_e_161b0, begin=0x651161b0, end=0x651161b0 + 15)
    # ---- run164 s22: finalize-tail + reach markers (observational only) ----
    def _s22_log(_msg):
        log(f'  [s22] {_msg}')
    def _s22_singleton_bc():
        try:
            _sg = e.r32(0x65144f20)
            if not _sg: return 'singleton=NULL'
            return f'singleton={_sg:#x} +0xbc={e.rd(_sg + 0xbc, 1)[0]} +0x0={e.r32(_sg):#x}'
        except Exception as _ex:
            return f'singleton-read-failed {_ex!r}'
    def _s22_ca30(uc_, addr, size, _u):
        try:
            _esp = uc_.reg_read(UC_X86_REG_ESP); _ecx = uc_.reg_read(UC_X86_REG_ECX)
            _s22_log(f'ca30 ENTRY this={_ecx:#x} ret={e.r32(_esp):#x} {_s22_singleton_bc()}')
        except Exception as _ex: _s22_log(f'ca30 hook failed {_ex!r}')
    uc.hook_add(UC_HOOK_CODE, _s22_ca30, begin=0x6510ca30, end=0x6510ca30 + 15)
    def _s22_mk(_addr, _msg):
        def _cb(uc_, addr, size, _u):
            try: _s22_log(_msg(uc_) if callable(_msg) else _msg)
            except Exception as _ex: _s22_log(f'hook @{_addr:#x} failed {_ex!r}')
        uc.hook_add(UC_HOOK_CODE, _cb, begin=_addr, end=_addr + 15)
    _s22_mk(0x6510cbfc, 'ca30: migration-ok omglog CALL site reached (push done, about to call)')
    _s22_mk(0x6510cc02, 'ca30: omglog RETURNED (cc02)')
    _s22_mk(0x6510cc57, 'ca30: (0x50a) THROW call site reached (cc57)')
    _s22_mk(0x6510ccc9, lambda uc_: f'ca30: DONE tail entered (ccc9, before a950 call) {_s22_singleton_bc()}')
    _s22_mk(0x6510ccd0, 'ca30: a950 RETURNED (ccd0)')
    def _s22_store(uc_, addr, size, _u):
        try:
            _edi = uc_.reg_read(UC_X86_REG_EDI); _eax = uc_.reg_read(UC_X86_REG_EAX)
            _old = e.rd(_edi + 0xbc, 1)[0] if _edi else None
            _s22_log(f'ca30: +0xbc STORE site (cce5): obj={_edi:#x} value={_eax} old+0xbc={_old}')
        except Exception as _ex: _s22_log(f'store hook failed {_ex!r}')
    uc.hook_add(UC_HOOK_CODE, _s22_store, begin=0x6510cce5, end=0x6510cce5 + 15)
    def _s22_a950(uc_, addr, size, _u):
        try:
            _esp = uc_.reg_read(UC_X86_REG_ESP); _ecx = uc_.reg_read(UC_X86_REG_ECX)
            _s22_log(f'FUN_6510a950 (finalize) ENTRY this={_ecx:#x} ret={e.r32(_esp):#x}')
        except Exception as _ex: _s22_log(f'a950 hook failed {_ex!r}')
    uc.hook_add(UC_HOOK_CODE, _s22_a950, begin=0x6510a950, end=0x6510a950 + 15)
    def _s22_8840(uc_, addr, size, _u):
        try:
            _esp = uc_.reg_read(UC_X86_REG_ESP); _ecx = uc_.reg_read(UC_X86_REG_ECX)
            _args = [e.r32(_esp + 4 + 4 * _i) for _i in range(4)]
            _s22_log(f'FUN_65108840 (maclist verify) REACHED this={_ecx:#x} args={[hex(_a) for _a in _args]} ret={e.r32(_esp):#x}')
        except Exception as _ex: _s22_log(f'8840 hook failed {_ex!r}')
    uc.hook_add(UC_HOOK_CODE, _s22_8840, begin=0x65108840, end=0x65108840 + 15)
    log('run164 s22 instrumentation installed (finalize tail + reach markers; no other change vs 163)')
    log('run160 s21 instrumentation installed')



    log('calling FUN_6511D680 (manager bootstrap) ...')
    # Trace every write into the native frame band during the D680 call
    # so the initialization (or absence) of the per-cycle continuation
    # frames can be attributed to specific guest PCs (readout #20).
    from unicorn import UC_HOOK_MEM_WRITE
    e.stack_writes = []
    def _wr(uc_, access, address, size, value, ud):
        if 0xF3FD000 <= address < 0xF3FE000 and len(e.stack_writes) < 400000:
            e.stack_writes.append((uc_.reg_read(_EIP), address, size, value))
    uc.hook_add(UC_HOOK_MEM_WRITE, _wr)
    e.vm_writes = []
    def _wrv(uc_, access, address, size, value, ud):
        if 0xDEE0000 <= address < 0xDF20000 and len(e.vm_writes) < 400000:
            e.vm_writes.append((uc_.reg_read(_EIP), address, size, value))
    uc.hook_add(UC_HOOK_MEM_WRITE, _wrv)
    def _wr0(uc_, access, address, size, value, ud):
        if address < 0x10:
            pc = uc_.reg_read(_EIP)
            log(f'  [wr0] write to {address:#x} size={size} val={value:#x} '
                f'pc={pc:#x} esp={uc_.reg_read(_ESP):#x}')
            if address == 0 and value == 0:
                parts = []
                for n, r in (('eax', UC_X86_REG_EAX), ('ecx', UC_X86_REG_ECX),
                             ('edx', UC_X86_REG_EDX), ('ebx', UC_X86_REG_EBX),
                             ('ebp', UC_X86_REG_EBP), ('esi', UC_X86_REG_ESI),
                             ('edi', UC_X86_REG_EDI)):
                    parts.append('%s=%#x' % (n, uc_.reg_read(r)))
                code = bytes(uc_.mem_read(pc - 16, 40)).hex()
                log('  [wr0] ZEROING: regs=' + ' '.join(parts) +
                    ' code@pc-16=' + code)
    uc.hook_add(UC_HOOK_MEM_WRITE, _wr0)
    try:
        log(f'  [shim67] pre-D680 slot[0x651390cc]={e.r32(0x651390cc):#x} '
            f'flag[0x65170a38]={e.r32(0x65170a38):#x}')
    except Exception as _ex:
        log(f'  [shim67] pre-D680 snapshot failed: {_ex}')
    ctx = run_with_seh(SAL_BASE + 0x1D680, label='D680')
    with open('/home/hatch/workspace/atrac-salwrap-work/unicorn/stack-writes125.txt', 'w') as f:
        for pc, a, sz, v in e.stack_writes:
            f.write(f'{pc:#x} {a:#x} {sz} {v:#x}\n')
    log(f'stack writes traced: {len(e.stack_writes)}')
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           'vm-writes111.txt'), 'w') as fh:
        for pc, a, sz, v in e.vm_writes:
            fh.write(f'{pc:#x} {a:#x} {sz} {v:#x}\n')
    log(f'vm writes traced: {len(e.vm_writes)}')
    log(f'manager ctx = {ctx:#x}')
    TRACE.append(('PHASE', 'post-D680'))

    # ---- run152: post-D680 analysis + controls + record-transplant drive ----
    log('=== run152 post-D680 analysis ===')
    _snap('post-D680')
    for _i in range(1, len(_SNAPS)):
        _t0, _b0 = _SNAPS[_i - 1]; _t1, _b1 = _SNAPS[_i]
        _diff = [j for j in range(min(len(_b0), len(_b1))) if _b0[j] != _b1[j]]
        if not _diff:
            log(f'run152 snapdiff {_t0} -> {_t1}: NO changes')
            continue
        _ranges = []
        _s = _p = _diff[0]
        for _j in _diff[1:]:
            if _j == _p + 1: _p = _j; continue
            _ranges.append((_s, _p)); _s = _p = _j
        _ranges.append((_s, _p))
        log(f'run152 snapdiff {_t0} -> {_t1}: {len(_diff)} bytes in {len(_ranges)} ranges: ' +
            ', '.join(f'+{a:#x}..+{b:#x}' for a, b in _ranges[:28]))
    try:
        log(f'run152 globals: DAT_6516d484={e.r32(0x6516d484):#x} DAT_6516d488={e.r32(0x6516d488):#x} DAT_6516b07c={e.r32(0x6516b07c):#x}')
    except Exception as _ex:
        log(f'run152 globals read failed: {_ex!r}')
    for _k in sorted(_RECS):
        log(f'run152 captured record len={_k:#x}: {_RECS[_k].hex(" ")}')
    _TRIM21 = True   # session 21: phase-trimmed probe (skip OP-A replay + after-opa controls)
    # ================= SESSION 21c: single-address observational hooks
    # (register reads via uc.reg_read -- run 162's e.r32(_eax) bug)
    def _s21b_hook(addr, fn):
        def _cb(uc, address, size, ud):
            if address != addr:
                return
            try:
                fn(uc)
            except Exception as ex:
                log(f'  [s21c] hook@{addr:#x} err {ex!r}')
        return uc.hook_add(UC_HOOK_CODE, _cb, begin=addr, end=addr)
    _R = UC_X86_REG_EAX
    _s21b_hook(0x6510cbcf, lambda uc: log(
        f"  [s21c] gate1 FUN_65103a20 -> AL={uc.reg_read(UC_X86_REG_EAX) & 0xff:#x}"))
    _s21b_hook(0x6510cbd8, lambda uc: log(
        f"  [s21c] gate2 FUN_65114d50 -> EAX={uc.reg_read(UC_X86_REG_EAX):#x}"))
    _s21b_hook(0x6510cbe2, lambda uc: log(
        f"  [s21c] ca30 -> 8ea0 out-pointer ESI={uc.reg_read(UC_X86_REG_ESI):#x}"))
    def _cbea(uc):
        esi = uc.reg_read(UC_X86_REG_ESI)
        flag = e.rd(esi, 1)[0] if esi else None
        log(f"  [s21c] 8ea0 returned AL={uc.reg_read(UC_X86_REG_EAX) & 0xff:#x} "
            f"out={esi:#x} *out={flag}")
    _s21b_hook(0x6510cbea, _cbea)
    _s21b_hook(0x6510cbf7, lambda uc: log('  [s21c] ca30: migration-ok log call'))
    _s21b_hook(0x6510cc0e, lambda uc: log('  [s21c] ca30 branch: closeCore + (0x50a)'))
    _s21b_hook(0x6510cc5c, lambda uc: log('  [s21c] ca30 branch: RESTORE BLOCK'))
    _s21b_hook(0x6510ccc9, lambda uc: log('  [s21c] ca30 branch: DONE -> finalize a950'))
    _s21b_hook(0x6510cd13, lambda uc: log('  [s21c] ca30 CATCH reset (+0xbc:=0)'))
    _s21b_hook(0x6510a950, lambda uc: log('  [s21c] FUN_6510a950 finalize entry'))
    def _ea0(uc):
        esp = uc.reg_read(UC_X86_REG_ESP)
        log(f"  [s21c] 8ea0 entry: this={uc.reg_read(UC_X86_REG_ECX):#x} "
            f"out={e.r32(esp + 4):#x}")
    _s21b_hook(0x65108ea0, _ea0)
    def _gfa(uc):
        log(f"  [s21c] 8ea0 GFA file={e.cstr(uc.reg_read(UC_X86_REG_ESI))!r} "
            f"-> EAX={uc.reg_read(UC_X86_REG_EAX):#x}")
    _s21b_hook(0x65108f50, _gfa)
    def _8330ret(uc):
        esp = uc.reg_read(UC_X86_REG_ESP)
        size = e.r32(esp + 0xd0); cap = e.r32(esp + 0xd4)
        dp = e.r32(esp + 0xc0) if cap >= 0x10 else esp + 0xc0
        seed = ''
        if 0 < size <= 64:
            try: seed = e.rd(dp, size).hex()
            except Exception: seed = '<unreadable>'
        log(f"  [s21c] 8330 ret in 8ea0: AL={uc.reg_read(UC_X86_REG_EAX) & 0xff:#x} "
            f"seedsize={size} seedcap={cap} seed={seed!r}")
    _s21b_hook(0x65108ff6, _8330ret)
    _s21b_hook(0x651090f9, lambda uc: log('  [s21c] 8ea0 branch: DIRECT PATH'))
    _s21b_hook(0x651091cf, lambda uc: log('  [s21c] 8ea0 branch: SUB-PATH'))
    _s21b_hook(0x651091a1, lambda uc: log('  [s21c] 8ea0: *out := 1 (91a1)'))
    _s21b_hook(0x651091c0, lambda uc: log('  [s21c] 8ea0: *out := 1 (91c0)'))
    _s21b_hook(0x65109131, lambda uc: log('  [s21c] 8ea0: (0x307) throw site'))
    _s21b_hook(0x65109325, lambda uc: log(
        f"  [s21c] 8ea0 return point 9325: EAX={uc.reg_read(UC_X86_REG_EAX):#x}"))
    log('run163 s21c single-address instrumentation installed')
    # ---- controls ----
    log('=== run152 controls ===')
    TRACE.append(('PHASE', 'controls-baseline'))
    def _mkstr(_txt):
        _a = e.alloc.alloc(32, 'b650str')
        _b = _txt.encode() + b'\x00'
        e.wr(_a, b'\x00' * 32)
        e.wr(_a + 4, _b)
        e.w32(_a + 0x14, len(_txt))
        e.w32(_a + 0x18, 15)
        return _a
    _devsal = open(_os.path.join(SONY_DIR, 'device.sal'), 'rb').read()
    def _ctl(_tag):
        try:
            _spec = _mkstr('Encrypt'); _name = _mkstr('Encrypt')
            _out = e.alloc.alloc(64, 'b650out'); e.wr(_out, b'\x00' * 64)
            _r = run_with_seh(SAL_BASE + 0x1b650, args=(_spec, _out, _name), ecx=ctx, label=f'run152 b650 {_tag}')
            _od = e.rd(_out, 64)
            _osz = int.from_bytes(_od[0x14:0x18], 'little')
            _ob = _od[4:4 + min(_osz, 40)] if _osz < 4096 else b''
            log(f'run152 b650 {_tag}: EAX={_r:#x} out size={_osz} hex={_ob.hex(" ")}')
        except Exception as _ex:
            log(f'run152 b650 {_tag} failed: {_ex!r}')
        try:
            _p = e.alloc.alloc(16, 'getout'); e.wr(_p, b'\x00' * 16)
            _live = (e.r32(ctx), e.r32(ctx + 4), e.r32(ctx + 8))
            _r = run_with_seh(SAL_BASE + 0x163f0, args=(_p, _p + 4, _p + 8), ecx=ctx, label=f'run152 getter {_tag}')
            _got = (e.r32(_p), e.r32(_p + 4), e.r32(_p + 8))
            log(f'run152 getter {_tag}: match={_got == _live}')
        except Exception as _ex:
            log(f'run152 getter {_tag} failed: {_ex!r}')
        try:
            _o = e.alloc.alloc(64, 'imgout'); e.wr(_o, b'\x00' * 64)
            _r = run_with_seh(SAL_BASE + 0x1ac50, args=(_o,), ecx=ctx, label=f'run152 getimage {_tag}')
            _sz = e.r32(_o + 0x14); _cap = e.r32(_o + 0x18)
            if 0 < _sz < 1000000:
                _dp = _o + 4 if _cap < 0x10 else e.r32(_o + 4)
                _d = e.rd(_dp, _sz)
                log(f'run152 getimage {_tag}: size={_sz} ==device.sal: {_d == _devsal}')
            else:
                log(f'run152 getimage {_tag}: size={_sz} (unexpected)')
        except Exception as _ex:
            log(f'run152 getimage {_tag} failed: {_ex!r}')
    _ctl('baseline')
    # ---- SESSION 21 TRIM: OP-A replay + after-opa controls skipped ----
    if not _TRIM21:
        # ---- run152: driver-faithful OP-A replay via live ctx vtable ----
        log('=== run152 OP-A replay ===')
        TRACE.append(('PHASE', 'opa-replay'))
        import struct as _st124
        _mgr = 0x651411dc
        _vt = e.r32(_mgr)
        log(f'run152 manager cell={_mgr:#x} *cell (vtable)={_vt:#x} (D680 ctx={ctx:#x})')
        _slots = {}
        for _off in range(0, 0xa8, 4):
            _slots[_off] = e.r32(_vt + _off)
        log('run152 live vtable: ' + ' '.join(f'+{_o:#x}={_slots[_o]:#x}' for _o in (0x0, 0x8, 0x40, 0x64, 0x68, 0x6c, 0x70, 0x74, 0x80, 0x84, 0x8c, 0x9c)))
        def _call124(_off, _args, _tag):
            try:
                _r = run_with_seh(_slots[_off], args=_args, ecx=_mgr, label=f'run152 {_tag}')
                log(f'run152 {_tag}: slot+{_off:#x} -> EAX={_r:#x}')
                return _r
            except Exception as _ex:
                log(f'run152 {_tag}: slot+{_off:#x} raised: {_ex!r}')
                return None
        _p16 = _call124(0x8, (), 'vt8-getter')
        if _p16:
            try: log(f'run152 vt8 16 bytes @ {_p16:#x}: {bytes(e.rd(_p16, 16)).hex(" ")}')
            except Exception as _ex: log(f'run152 vt8 dump failed: {_ex!r}')
        def _mkstream(_tag):
            _cell = e.alloc.alloc(4, _tag + 'cell'); e.wr(_cell, b'\x00' * 4)
            _h = _call124(0x40, (0x200,), _tag + '-ctor')
            if _h is not None: e.wr(_cell, _st124.pack('<I', _h))
            return _cell, _h
        _sin_cell, _sin = _mkstream('sIn')
        _sout_cell, _sout = _mkstream('sOut')
        def _dumpstream(_cell, _h, _tag):
            if not _h: return
            try:
                _obj = bytes(e.rd(_h, 0x90))
                log(f'run152 {_tag}: stream obj @{_h:#x} (0x90B): {_obj.hex(" ")}')
                for _fo in range(0, 0x90, 4):
                    _p = _st124.unpack_from('<I', _obj, _fo)[0]
                    if 0x10000000 <= _p < 0x11000000 or 0x65100000 <= _p < 0x65170000:
                        try:
                            _d = bytes(e.rd(_p, 48))
                            if any(_d): log(f'run152 {_tag}: obj+{_fo:#x} -> {_p:#x}: {_d.hex(" ")}')
                        except Exception: pass
            except Exception as _ex:
                log(f'run152 {_tag}: stream dump failed: {_ex!r}')
        _dumpstream(_sin_cell, _sin, 'sIn-fresh')
        if _p16:
            _desc16 = e.alloc.alloc(8, 'desc16'); e.wr(_desc16, _st124.pack('<II', _p16, 16))
            _call124(0x6c, (_sin_cell, _desc16), 'write-octet16')
        _call124(0x74, (_sin_cell, 0, 0), 'write-int0')
        _md = e.alloc.alloc(0x30, 'moddesc'); e.wr(_md, b'\x00' * 0x30)
        e.wr(_md + 8 + 4, b'atpcd.ocm\x00')
        e.wr(_md + 8 + 0x14, _st124.pack('<II', 9, 0xf))
        _call124(0x64, (_sin_cell, _md), 'write-module')
        _dumpstream(_sin_cell, _sin, 'sIn-built')
        _call124(0x0, (_sin_cell, _sout_cell, 0, 0), 'EXECUTE')
        _dumpstream(_sout_cell, _sout, 'sOut-after')
        _obyte = e.alloc.alloc(4, 'obyte'); e.wr(_obyte, b'\xee' * 4)
        _call124(0x8c, (_sout_cell, _obyte), 'read-byte')
        log(f'run152 read-byte result: {bytes(e.rd(_obyte, 4)).hex(" ")}')
        _obuf16 = e.alloc.alloc(16, 'obuf16'); e.wr(_obuf16, b'\xdd' * 16)
        _odesc = e.alloc.alloc(8, 'odesc'); e.wr(_odesc, _st124.pack('<II', _obuf16, 16))
        _call124(0x84, (_sout_cell, _odesc), 'read-buf16')
        log(f'run152 read-buf16 result: {bytes(e.rd(_obuf16, 16)).hex(" ")} desc now {bytes(e.rd(_odesc, 8)).hex(" ")}')
        for _si in (1, 2):
            _ostr2 = e.alloc.alloc(0x1c, f'ostr{_si}'); e.wr(_ostr2, b'\x00' * 0x1c)
            _call124(0x80, (_sout_cell, _ostr2), f'read-str{_si}')
            _ln = e.r32(_ostr2 + 0x14); _cap = e.r32(_ostr2 + 0x18)
            _dp = _ostr2 + 4 if _cap < 0x10 else e.r32(_ostr2 + 4)
            try: _sb = bytes(e.rd(_dp, min(_ln, 200))) if _ln else b''
            except Exception: _sb = b'<unreadable>'
            log(f'run152 read-str{_si}: len={_ln} cap={_cap} bytes={_sb!r}')
        _ctl('after-opa')
    else:
        log('run160 TRIM: OP-A replay + after-opa controls SKIPPED')
        TRACE.append(('PHASE', 'opa-skipped'))

    # ---- run152: identity string dump (holder DAT_6516b0ac, string at +0x20) ----
    try:
        _hold = 0x6516b0ac
        _str = _hold + 0x20
        _sz = e.r32(_str + 0x14); _cap = e.r32(_str + 0x18)
        _dp = e.r32(_str + 4) if _cap >= 0x10 else _str + 4
        _data = bytes(e.rd(_dp, _sz)) if 0 < _sz < 4096 else b''
        _genuine = open(_os.path.join(SONY_DIR, 'OMGKEY', 'omg_id.dat'), 'rb').read()
        log(f'run152 identity string: holder={_hold:#x} initflag={e.r32(_hold + 0x34):#x} size={_sz} cap={_cap} data@{_dp:#x}: {_data.hex(" ")}')
        log(f'run152 identity == corpus omg_id.dat: {_data == _genuine}; bytes[4:20]={_data[4:20].hex(" ")}')
        log('run152 ekbw counts (pre-pfcom): ' + ', '.join(f'{_EKBW[a]} x{_EKBWC.get(a, 0)}' for a in sorted(_EKBW)))
    except Exception as _ex:
        log(f'run152 identity dump failed: {_ex!r}')

    # ---- run152: pfcom.dll (the "procfile" factory) load + session mapping ----
    log('=== run152 pfcom probe ===')
    TRACE.append(('PHASE', 'pfcom-probe'))
    _AUDIT['on'] = True
    _audit('WINDOW', mark='pfcom-probe-start')
    PF_BASE = 0x64700000
    pf_exports = {}
    try:
        EXPORTS.update(sal_exports)
        _pf_path = _os.path.join(SONY_DIR, 'pfcom.dll')
        _nstub0 = len(e.stubs)
        pf_exports = e.load_pe(_pf_path, PF_BASE, True)
        log(f'run152 pfcom loaded at {PF_BASE:#x}: {len(pf_exports)} exports; procfile={pf_exports.get("procfile", 0):#x}')
        _newun = [nm for nm, h, c, n in e.stubs[_nstub0:] if h is None]
        log(f'run152 pfcom stubs added: {len(e.stubs) - _nstub0}, unresolved: {_newun[:24]}')
        import pefile as _pfpe
        _epf = PF_BASE + _pfpe.PE(_pf_path).OPTIONAL_HEADER.AddressOfEntryPoint
        _r = e.call(_epf, args=(PF_BASE, 1, 0), label='pfcom DllMain')
        log(f'run152 pfcom entry returned {_r:#x}; stop={e.stop_reason}')
        e.stop_reason = None
        while INITQ:
            _qb, _qe = INITQ.pop(0)
            for _ptr in range(_qb, _qe, 4):
                _fn = e.r32(_ptr)
                if _fn:
                    e.call(_fn, label=f'pfcom static ctor {_fn:#x}')
                    e.stop_reason = None
            log(f'run152 pfcom init table {_qb:#x}..{_qe:#x} drained')
    except Exception as _ex:
        log(f'run152 pfcom load failed: {_ex!r}')
    log('run152 pfcom probe: slab write-watch has been armed since main() start')
    _fac = 0
    if pf_exports.get('procfile'):
        try:
            _fac = e.call(pf_exports['procfile'], args=(), label='run152 procfile()')
            log(f'run152 procfile() -> EAX={_fac:#x}; stop={e.stop_reason}')
            e.stop_reason = None
        except Exception as _ex:
            log(f'run152 procfile() failed: {_ex!r}')
    def _dumptable(_obj, _tag, _n=0x24):
        if not _obj:
            return 0
        try:
            _vt = e.r32(_obj)
            log(f'run152 {_tag}: obj={_obj:#x} vtable={_vt:#x}')
            _line = []
            for _o in range(0, _n * 4, 4):
                _t = e.r32(_vt + _o)
                _in = 'PF' if PF_BASE <= _t < PF_BASE + 0x32000 else ('SAL' if 0x65100000 <= _t < 0x65170000 else ('OMG' if 0x63900000 <= _t < 0x63a00000 else '??'))
                _line.append(f'+{_o:#x}={_t:#x}[{_in}]')
            log(f'run152 {_tag} slots: ' + ' '.join(_line))
            return _vt
        except Exception as _ex:
            log(f'run152 {_tag} vtable dump failed: {_ex!r}')
            return 0
    _facvt = _dumptable(_fac, 'factory')
    # secure header of TRK000A0.ATP (host-read; evidence files untouched)
    _atp = open('/home/hatch/workspace/atrac-cd-stage0/CD stuff/HIFI/TRK000A0.ATP', 'rb').read()
    _hdr = _atp[1024:1120]
    log(f'run152 A0 hdr96: {_hdr.hex(" ")}')
    log(f'run152 A0 seed(hdr+0x18)={_hdr[0x18:0x20].hex(" ")} iv(hdr+0x58)={_hdr[0x58:0x60].hex(" ")}')
    _hbuf = e.alloc.alloc(0x100, 'a0hdr'); e.wr(_hbuf, _hdr + b'\x00' * (0x100 - len(_hdr)))
    _sess = 0
    _heap_before = None
    try:
        _heap_before = bytes(e.rd(HEAP_BASE, e.alloc.brk - HEAP_BASE))
        log(f'run152 heap snapshot before vt+8: {len(_heap_before)} bytes (brk={e.alloc.brk:#x})')
    except Exception as _ex:
        log(f'run152 heap snapshot failed: {_ex!r}')
    TRACE.append(('PHASE', 'vt8-start'))
    if _facvt:
        try:
            _f8 = e.r32(_facvt + 8)
            _sess = run_with_seh(_f8, args=(_hbuf + 0x20,), ecx=_fac, label='run152 factory vt+8 (sess create)')
            log(f'run152 factory vt+8(hdr+0x20) -> EAX={_sess:#x}')
        except Exception as _ex:
            log(f'run152 factory vt+8 failed: {_ex!r}')
    if _heap_before is not None:
        try:
            _heap_after = bytes(e.rd(HEAP_BASE, e.alloc.brk - HEAP_BASE))
            _common = min(len(_heap_before), len(_heap_after))
            _di = [j for j in range(_common) if _heap_before[j] != _heap_after[j]]
            log(f'run152 heap diff vt+8: {len(_di)} bytes changed in common region; brk {_heap_before and len(_heap_before)} -> {len(_heap_after)}')
            _ranges = []
            if _di:
                _s = _p = _di[0]
                for _j in _di[1:]:
                    if _j == _p + 1: _p = _j; continue
                    _ranges.append((_s, _p)); _s = _p = _j
                _ranges.append((_s, _p))
            for (_ra, _rb) in _ranges[:36]:
                _ln = min(_rb - _ra + 1, 48)
                log(f'  [heap129] @{HEAP_BASE + _ra:#x} len={_rb - _ra + 1}: before={_heap_before[_ra:_ra + _ln].hex(" ")} after={_heap_after[_ra:_ra + _ln].hex(" ")}')
            if len(_ranges) > 36:
                log(f'  [heap129] ... and {len(_ranges) - 36} more ranges')
        except Exception as _ex:
            log(f'run152 heap diff failed: {_ex!r}')
    TRACE.append(('PHASE', 'vt8-end'))
    log(f"run152 slab write-watch at vt8-end: {_WS['n']} writes in slab ({_WS['logged']} logged); REC@0x107eb310: {bytes(e.rd(0x107eb310, 100)).hex(' ')}")
    _audit('WINDOW', mark='vt8-end')
    _AUDIT['on'] = False
    try:
        import json as _json150
        with open('audit150.json', 'w') as _jf:
            _json150.dump([[k, {kk: (vv if isinstance(vv, (str, int, float, bool, type(None))) else repr(vv)) for kk, vv in v.items()}] for k, v in _AUDIT['rows']], _jf, indent=1)
        log(f'run152 audit: {len(_AUDIT["rows"])} rows -> audit150.json')
    except Exception as _ex:
        log(f'run152 audit dump failed: {_ex!r}')
    try:
        log('run152 ekbw counts (final): ' + ', '.join(f'{_EKBW[a]} x{_EKBWC.get(a, 0)}' for a in sorted(_EKBW)))
    except Exception as _ex:
        log(f'run152 ekbw final counts failed: {_ex!r}')
    _svt = _dumptable(_sess, 'session', 0x30)
    if _sess:
        try: log(f'run152 session obj mem[0:0x60]: {bytes(e.rd(_sess, 0x60)).hex(" ")}')
        except Exception: pass
    if _svt:
        try:
            _r74 = run_with_seh(e.r32(_svt + 0x74), args=(0xe,), ecx=_sess, label='run152 sess vt+0x74(0xe)')
            log(f'run152 sess vt+0x74(0xe) -> EAX={_r74:#x}')
        except Exception as _ex:
            log(f'run152 sess vt+0x74 failed: {_ex!r}')
        _strbuf = e.alloc.alloc(0x20, 'pfstr'); e.wr(_strbuf, b'\x00' * 0x20)
        try:
            _r28 = run_with_seh(e.r32(_svt + 0x28), args=(_strbuf,), ecx=_sess, label='run152 sess vt+0x28(&str)')
            log(f'run152 sess vt+0x28 -> EAX={_r28:#x}')
            log(f'run152 pfstr after: {bytes(e.rd(_strbuf, 0x20)).hex(" ")}')
            for _cand, _ctag in ((_strbuf, 'arg-str'), (_r28, 'ret-ptr')):
                if _cand and 0x10000000 <= _cand < 0x11000000 or (_cand and PF_BASE <= _cand < PF_BASE + 0x32000) or (_cand and 0x65100000 <= _cand < 0x65170000):
                    try:
                        _sz = e.r32(_cand + 0x14); _cap = e.r32(_cand + 0x18)
                        _dp = _cand + 4 if _cap < 0x10 else e.r32(_cand + 4)
                        _sb = bytes(e.rd(_dp, min(_sz, 128))) if 0 < _sz < 0x10000 else b''
                        log(f'run152 {_ctag} @{_cand:#x}: size={_sz} cap={_cap} data={_sb.hex(" ")}')
                    except Exception as _ex:
                        log(f'run152 {_ctag} read failed: {_ex!r}')
            try: log(f'run152 session obj mem after[0:0x60]: {bytes(e.rd(_sess, 0x60)).hex(" ")}')
            except Exception: pass
        except Exception as _ex:
            log(f'run152 sess vt+0x28 failed: {_ex!r}')
    _ctl('after-pfcom')
    log('=== run152 pfcom post-mortem ===')
    try: _dump_pf('post-mortem')
    except Exception as _ex: log(f'run152 post-mortem failed: {_ex!r}')

    log('=== run152 done ===')
    # ---- run152: census summary ----
    log('=== run152 census summary ===')
    for _win in sorted(_CB17['counts']):
        _c = _CB17['counts'][_win]
        log(f'  [cb152] window {_win}: {sum(_c.values())} HLE calls, {len(_c)} distinct')
        for _nm, _n in sorted(_c.items(), key=lambda kv: -kv[1]):
            log(f'  [cb152]   {_win} :: {_nm} x{_n}')
    log(f'  [cb152] flagged detail ({len(_CB17["detail"])} lines):')
    for _d in _CB17['detail']:
        log(f'  [cb152]   {_d[0]} :: {_d[1]} args={_d[2]} -> {_d[3]} retaddr={_d[4]}')




    gp = getattr(e, 'grow_pcs', {})
    if gp:
        top = sorted(gp.items(), key=lambda kv: -kv[1])[:6]
        log('stack-growth fault PCs: ' +
            ', '.join(f'{pc:#x}x{n}' for pc, n in top))
    log(f'trace: {len(TRACE)} HLE calls; allocs: {len(ALLOC_LEDGER)}')
    for t in TRACE[:120]:
        log('   ', t)
    if len(TRACE) > 120:
        log('   ... last 20:')
        for t in TRACE[-20:]: log('   ', t)
    with open('/home/hatch/workspace/atrac-salwrap-work/unicorn/trace128.txt', 'w') as _tf:
        for _t in TRACE:
            _tf.write(repr(_t) + '\n')
    log(f'full trace dumped ({len(TRACE)} calls)')
    big = sorted(ALLOC_LEDGER, key=lambda r: -r[1])[:15]
    log('largest allocations:')
    for a, s, tag in big: log(f'   {a:#010x} {s:#x} ({s}) {tag}')
    # scan committed regions for formed-image signature: name + 'bc' marker.
    log('scanning heap for image markers ...')
    import re
    heap = e.rd(HEAP_BASE, e.alloc.brk - HEAP_BASE)
    for m in re.finditer(rb'[\x20-\x7e]{3,40}\.ocm', heap):
        log(f'   ocm name near heap {HEAP_BASE + m.start():#x}: {m.group()!r}')
    for m in re.finditer(rb'bc\x00', heap[:0]):
        pass
    with open('/home/hatch/workspace/atrac-salwrap-work/unicorn/heap-dump115.bin', 'wb') as f:
        f.write(heap)
    log(f'heap dumped ({len(heap)} bytes)')
    try:
        with open('/home/hatch/workspace/atrac-salwrap-work/unicorn/image-data128.bin', 'wb') as f:
            f.write(e.uc.mem_read(0x65141000, 0x30000))
        log('image .data dumped')
    except Exception as ex:
        log(f'image .data dump failed: {ex}')
    try:
        buf = bytearray()
        for p in range(0xF3FC000, 0xF3FE000, 0x1000):
            try: buf += e.uc.mem_read(p, 0x1000)
            except Exception: buf += b'\xee' * 0x1000
        with open('/home/hatch/workspace/atrac-salwrap-work/unicorn/stack-dump111.bin', 'wb') as f:
            f.write(bytes(buf))
        log('stack dumped')
    except Exception as ex:
        log(f'stack dump failed: {ex}')

# (entry point lives at the very end of the file, after all HLE tables)

# ================================================================ batch 2
import socket as _socket
def h_GetSystemTimeAsFileTime(e, a, x):
    import time as _t
    ft = int((1793313847 + 11644473600) * 10_000_000)  # run152 FROZEN
    e.wr(a[0], struct.pack('<Q', ft)); return 0
def h_htonl(e, a, x):  return struct.unpack('>I', struct.pack('<I', a[0]))[0]
def h_ntohl(e, a, x):  return struct.unpack('<I', struct.pack('>I', a[0]))[0]
def h_GetThreadContext(e, a, x):
    flags = e.r32(a[1]) if a[1] else 0
    e.wr(a[1], b'\0' * 716); e.w32(a[1], flags)
    return 1
def h_SetFileAttributes(e, a, x):  return 1
def h_DeleteFileA(e, a, x):
    _p = e.cstr(a[0]); hp = host_path(_p)
    _ex = bool(hp and _os.path.exists(hp))
    _audit('DeleteFile', win=_p, host=hp, existed=_ex, result=1)
    if hp and _os.path.exists(hp):
        try: _os.remove(hp)
        except OSError: pass
    return 1
def h_RemoveDirectory(e, a, x):
    hp = host_path(e.cstr(a[0]))
    if hp and _os.path.isdir(hp):
        try: _os.rmdir(hp)
        except OSError: pass
    return 1
def h_CreateDirectory(e, a, x):
    _p = e.cstr(a[0]); hp = host_path(_p)
    _audit('CreateDirectory', win=_p, host=hp, result=1)
    if hp:
        try: _os.makedirs(hp, exist_ok=True)
        except OSError: pass
    return 1
def h_CopyFileA(e, a, x):
    import shutil
    _ps, _pd = e.cstr(a[0]), e.cstr(a[1])
    s, d = host_path(_ps), host_path(_pd)
    _r = 0
    if s and d and _os.path.exists(s):
        try: shutil.copyfile(s, d); _r = 1
        except OSError: _r = 0
    _audit('CopyFile', src=_ps, dst=_pd, shost=s, dhost=d, result=_r)
    return _r
def h_MoveFileA(e, a, x):
    _ps, _pd = e.cstr(a[0]), e.cstr(a[1])
    s, d = host_path(_ps), host_path(_pd)
    _r = 0
    if s and d and _os.path.exists(s):
        try: _os.replace(s, d); _r = 1
        except OSError: _r = 0
    _audit('MoveFile', src=_ps, dst=_pd, shost=s, dhost=d, result=_r)
    return _r
def h_GetFullPathNameA(e, a, x):
    p = e.cstr(a[0])
    if not (len(p) > 1 and p[1] == ':'):
        p = 'C:\\' + p.lstrip('\\')
    if a[2]: e.wr(a[2], p.encode('latin-1')[:a[2] - 1] + b'\0')
    return len(p)
def h_FormatMessageA(e, a, x):
    # FORMAT_MESSAGE_FROM_SYSTEM-ish: hand back a generic string
    msg = 'The operation completed successfully.\0'
    if a[6]:
        buf = e.alloc.alloc(len(msg) + 1, 'FormatMessage')
        e.put_cstr(buf, msg.rstrip('\0')); e.w32(a[6], buf)
        return len(msg) - 1
    if a[4]: e.wr(a[4], msg.encode('latin-1')[:a[5] - 1] + b'\0')
    return len(msg) - 1
def h_GetLocaleInfoA(e, a, x):
    vals = {0x1001: 'ENU', 0x409: 'en', 0x21009: ''}
    s = vals.get(a[1], '')
    if a[3]:
        if a[3] == 0: return len(s) + 1
        e.put_cstr(a[2], s)
    return len(s) + 1
# --- security descriptors / SIDs (benign but structurally plausible)
def h_InitSD(e, a, x):
    e.wr(a[0], b'\0' * 20); e.wr(a[0], b'\x01'); return 1
def h_InitAcl(e, a, x):
    e.wr(a[0], struct.pack('<BBHHH', 2, 0, a[1], 0, 0)); return 1
def h_AllocSid(e, a, x):
    n = a[8]
    sid = e.alloc.alloc(8 + 4 * n, 'SID')
    e.wr(sid, struct.pack('<BB', 1, n) + b'\0\0\0\0\0\5')
    for i in range(n): e.w32(sid + 8 + 4 * i, a[i])
    if a[9] if len(a) > 9 else False: pass
    return 1  # note: real API returns BOOL with pSid written via a[9]
def h_AllocSid2(e, a, x):
    # AllocateAndInitializeSid(auth, n, s0..s7, **pSid): args[10] = out ptr
    n = a[1]
    sid = e.alloc.alloc(8 + 4 * max(n, 1), 'SID')
    auth = e.rd(a[0], 6) if a[0] else b'\0\0\0\0\0\5'
    e.wr(sid, struct.pack('<BB', 1, n) + auth)
    for i in range(n): e.w32(sid + 8 + 4 * i, a[2 + i])
    e.w32(a[10], sid)
    return 1
def h_EqualSid_log(e, a, x):
    # run106 DIAGNOSTIC ONLY: log args before comparing (behavior identical to old lambda)
    def _sidinfo(_p):
        try:
            _h = e.rd(_p, 2)
            _n = 8 + 4 * _h[1]
            try:
                _b = e.rd(_p, min(_n, 32))
                return f'rev={_h[0]} cnt={_h[1]} len={_n} bytes={_b.hex(" ")}'
            except Exception as _ex2:
                return f'rev={_h[0]} cnt={_h[1]} len={_n} FULL-READ-FAILED: {_ex2!r}'
        except Exception as _ex:
            return f'UNREADABLE: {_ex!r}'
    log(f'  [eqsid] a0={a[0]:#x} ({_sidinfo(a[0])}) a1={a[1]:#x} ({_sidinfo(a[1])})')
    return 1 if e.rd(a[0], h_GetLengthSid(e, [a[0]], x)) == e.rd(a[1], h_GetLengthSid(e, [a[1]], x)) else 0
def h_GetLengthSid(e, a, x):
    return 8 + 4 * e.rd(a[0], 2)[1] if a[0] else 0
def h_CopySid(e, a, x):
    n = h_GetLengthSid(e, [a[1]], x)
    e.wr(a[0], e.rd(a[1], n)); return 1
def h_GetSidSubAuthority(e, a, x):
    return a[0] + 8 + 4 * a[1]
def h_OpenProcessToken(e, a, x):
    if a[2]: e.w32(a[2], 0x600)
    return 1
def h_GetTokenInformation(e, a, x):
    # run106: TokenGroups (class 2) now returns a real TOKEN_GROUPS. The old code
    # wrote TOKEN_USER-shaped data (SID pointer + 0) regardless of class, so the
    # OMGUtils privilege classifier (0x6391a0d0) read GroupCount = a SID pointer
    # and walked uninitialized heap as group entries -> EqualSid fault (run94).
    if a[1] == 2:
        _groups = [(32, 544, 7), (32, 545, 7)]  # Administrators + Users, enabled
        _need = 4 + 8 * len(_groups)
        if a[4]: e.w32(a[4], _need)
        if a[2] and a[3] >= _need:
            e.w32(a[2], len(_groups))
            for _i, (_s0, _rid, _at) in enumerate(_groups):
                _sid = e.alloc.alloc(16, 'SID group')
                e.wr(_sid, struct.pack('<BB', 1, 2) + b'\0\0\0\0\0\5' + struct.pack('<II', _s0, _rid))
                e.w32(a[2] + 4 + 8 * _i, _sid)
                e.w32(a[2] + 8 + 8 * _i, _at)
        return 1
    if a[4]: e.w32(a[4], 16)
    if a[2] and a[3] >= 8:
        sid = e.alloc.alloc(12, 'SID token')
        e.wr(sid, struct.pack('<BB', 1, 1) + b'\0\0\0\0\0\5' + struct.pack('<I', 1000))
        e.w32(a[2], sid); e.w32(a[2] + 4, 0)
    return 1
BATCH2 = {
 'GetSystemTimeAsFileTime': (h_GetSystemTimeAsFileTime, 'stdcall', 1),
 'htonl': (h_htonl, 'stdcall', 1), 'ntohl': (h_ntohl, 'stdcall', 1),
 'GetThreadContext': (h_GetThreadContext, 'stdcall', 2),
 'SetThreadContext': (h_ret1, 'stdcall', 2),
 'SuspendThread': (h_noop0, 'stdcall', 1), 'ResumeThread': (h_noop0, 'stdcall', 1),
 'SetFileAttributesA': (h_SetFileAttributes, 'stdcall', 2), 'SetFileAttributesW': (h_SetFileAttributes, 'stdcall', 2),
 'DeleteFileA': (h_DeleteFileA, 'stdcall', 1), 'DeleteFileW': (h_DeleteFileA, 'stdcall', 1),
 'RemoveDirectoryA': (h_RemoveDirectory, 'stdcall', 1), 'RemoveDirectoryW': (h_RemoveDirectory, 'stdcall', 1),
 'CreateDirectoryA': (h_CreateDirectory, 'stdcall', 2), 'CreateDirectoryW': (h_CreateDirectory, 'stdcall', 2),
 'CopyFileA': (h_CopyFileA, 'stdcall', 3), 'CopyFileW': (h_CopyFileA, 'stdcall', 3),
 'MoveFileA': (h_MoveFileA, 'stdcall', 2), 'MoveFileW': (h_MoveFileA, 'stdcall', 2),
 'GetFullPathNameA': (h_GetFullPathNameA, 'stdcall', 4), 'GetFullPathNameW': (h_GetFullPathNameA, 'stdcall', 4),
 'FormatMessageA': (h_FormatMessageA, 'stdcall', 7), 'FormatMessageW': (h_FormatMessageA, 'stdcall', 7),
 'GetLocaleInfoA': (h_GetLocaleInfoA, 'stdcall', 4), 'GetLocaleInfoW': (h_GetLocaleInfoA, 'stdcall', 4),
 'GetThreadLocale': (lambda e, a, x: 0x0409, 'stdcall', 0),
 'FindResourceA': (h_noop0, 'stdcall', 3), 'FindResourceW': (h_noop0, 'stdcall', 3),
 'LoadResource': (h_noop0, 'stdcall', 2), 'LockResource': (h_noop0, 'stdcall', 1),
 'SizeofResource': (h_noop0, 'stdcall', 2), 'FreeResource': (h_ret1, 'stdcall', 1),
 'CreateSemaphoreA': (lambda e, a, x: 0x508, 'stdcall', 4), 'ReleaseSemaphore': (h_ret1, 'stdcall', 3),
 'RegDeleteKeyA': (h_noop0, 'stdcall', 2), 'RegDeleteKeyW': (h_noop0, 'stdcall', 2),
 'RegDeleteValueA': (h_noop0, 'stdcall', 2),
 'InitializeSecurityDescriptor': (h_InitSD, 'stdcall', 2),
 'SetSecurityDescriptorDacl': (h_ret1, 'stdcall', 4),
 'SetSecurityDescriptorOwner': (h_ret1, 'stdcall', 3),
 'SetSecurityDescriptorGroup': (h_ret1, 'stdcall', 3),
 'GetSecurityDescriptorLength': (lambda e, a, x: 20, 'stdcall', 1),
 'GetSecurityDescriptorControl': (lambda e, a, x: (e.w32(a[1], 0x8004) if a[1] else 0, e.w32(a[2], 0) if a[2] else 0, 1)[2], 'stdcall', 3),
 'GetSecurityDescriptorDacl': (lambda e, a, x: (e.w32(a[1], 0) if a[1] else 0, e.w32(a[3], 0) if a[3] else 0, 1)[2], 'stdcall', 4),
 'GetSecurityDescriptorOwner': (lambda e, a, x: (e.w32(a[1], 0) if a[1] else 0, 1)[1], 'stdcall', 2),
 'GetSecurityDescriptorGroup': (lambda e, a, x: (e.w32(a[1], 0) if a[1] else 0, 1)[1], 'stdcall', 2),
 'GetSecurityDescriptorSacl': (lambda e, a, x: (e.w32(a[1], 0) if a[1] else 0, e.w32(a[3], 0) if a[3] else 0, 1)[2], 'stdcall', 4),
 'MakeSelfRelativeSD': (h_ret1, 'stdcall', 3), 'MakeAbsoluteSD': (h_ret1, 'stdcall', 11),
 'InitializeAcl': (h_InitAcl, 'stdcall', 3), 'AddAce': (h_ret1, 'stdcall', 3),
 'AddAccessAllowedAce': (h_ret1, 'stdcall', 4),
 'GetAclInformation': (h_ret1, 'stdcall', 4),
 'AllocateAndInitializeSid': (h_AllocSid2, 'stdcall', 11),
 'InitializeSid': (lambda e, a, x: (e.wr(a[0], struct.pack('<BB', 1, a[2]) + (e.rd(a[1], 6) if a[1] else b'\0'*6)), 1)[1], 'stdcall', 3),
 'GetLengthSid': (h_GetLengthSid, 'stdcall', 1), 'CopySid': (h_CopySid, 'stdcall', 3),
 'IsValidSid': (h_ret1, 'stdcall', 1),
 'EqualSid': (h_EqualSid_log, 'stdcall', 2),
 'GetSidLengthRequired': (lambda e, a, x: 8 + 4 * a[0], 'stdcall', 1),
 'GetSidSubAuthority': (h_GetSidSubAuthority, 'stdcall', 2),
 'GetSidSubAuthorityCount': (lambda e, a, x: a[0] + 1, 'stdcall', 1),
 'FreeSid': (h_noop0, 'stdcall', 1),
 'OpenProcessToken': (h_OpenProcessToken, 'stdcall', 3),
 'GetTokenInformation': (h_GetTokenInformation, 'stdcall', 5),
 'CoCreateGuid': (lambda e, a, x: (e.wr(a[0], bytes(range(16))), 0)[1], 'stdcall', 1),
 'StringFromGUID2': (h_StringFromGUID2, 'stdcall', 3),
 'IIDFromString': (h_IIDFromString, 'stdcall', 2),
 'SHGetSpecialFolderPathW': (h_SHGetFolderPathA, 'stdcall', 4),
 'SHGetSpecialFolderPathA': (h_SHGetFolderPathA, 'stdcall', 4),
 'wvsprintfA': (h_vsprintf, 'cdecl', 3), 'wvsprintfW': (h_vsprintf, 'cdecl', 3),
 # MSVC iostream / string extras (logging paths; benign)
 '?setf@ios_base@std@@QAEHHH@Z': (lambda e, a, x: 0, 'thiscall', 2),
 '??6?$basic_ostream@DU?$char_traits@D@std@@@std@@QAEAAV01@H@Z': (lambda e, a, x: x, 'thiscall', 1),
 '??6?$basic_ostream@DU?$char_traits@D@std@@@std@@QAEAAV01@P6AAAVios_base@1@AAV21@@Z@Z': (lambda e, a, x: x, 'thiscall', 1),
 '?setw@std@@YA?AU?$_Smanip@H@1@H@Z': (lambda e, a, x: (e.w32(a[0] + 4, a[1]), a[0])[1], 'cdecl', 2),
 '?size@?$basic_string@DU?$char_traits@D@std@@V?$allocator@D@2@@std@@QBEIXZ':
   (lambda e, a, x: e.r32(x + 0x14), 'thiscall', 0),
 '?unget@?$basic_istream@DU?$char_traits@D@std@@@std@@QAEAAV12@XZ': (lambda e, a, x: x, 'thiscall', 0),
 '?get@?$basic_istream@DU?$char_traits@D@std@@@std@@QAEAAV12@AAD@Z':
   (lambda e, a, x: (e.wr(a[0], b'\0'), x)[1], 'thiscall', 1),
 '??Bios_base@std@@QBEPAXXZ': (lambda e, a, x: x, 'thiscall', 0),
}
HLE.update(BATCH2)
# string insert / append-char need the string helpers; register separately
def h_str_insert(e, a, x):
    s = _sdata(e, x, 1); add = e.cstr(a[1])
    _sset(e, x, s[:a[0]] + add + s[a[0]:], 1); return x
def h_str_append_ch(e, a, x):
    _sappend(e, x, chr(a[0] & 0xFF), 1); return x
def h_str_append_wch(e, a, x):
    _sappend(e, x, chr(a[0] & 0xFFFF), 2); return x
HLE['?insert@?$basic_string@DU?$char_traits@D@std@@V?$allocator@D@2@@std@@QAEAAV12@IPBD@Z'] = (h_str_insert, 'thiscall', 2)
HLE['??Y?$basic_string@DU?$char_traits@D@std@@V?$allocator@D@2@@std@@QAEAAV01@D@Z'] = (h_str_append_ch, 'thiscall', 1)
HLE['??Y?$basic_string@GU?$char_traits@G@std@@V?$allocator@G@2@@std@@QAEAAV01@G@Z'] = (h_str_append_wch, 'thiscall', 1)

# (entry point at the very end of the file)

# ================================================================ batch 3
def h_rand(e, a, x):
    e._rand_seed = (getattr(e, '_rand_seed', 1) * 214013 + 2531011) & 0xFFFFFFFF
    return (e._rand_seed >> 16) & 0x7FFF
def h_srand(e, a, x):
    e._rand_seed = a[0]; return 0
BATCH_RAND = {
 'rand': (h_rand, 'cdecl', 0), 'srand': (h_srand, 'cdecl', 1),
 '_set_error_mode': (h_noop0, 'cdecl', 1), 'signal': (h_noop0, 'cdecl', 2),
 '_getpid': (lambda e, a, x: 4242, 'cdecl', 0),
}
HLE.update(BATCH_RAND)
def h_GetProcessAffinityMask(e, a, x):
    if a[1]: e.w32(a[1], 1)
    if a[2]: e.w32(a[2], 1)
    return 1
def h_GlobalMemoryStatusEx(e, a, x):
    e.w32(a[0] + 0, 64)
    e.w32(a[0] + 4, 50)                                  # dwMemoryLoad
    e.wr(a[0] + 8, struct.pack('<Q', 2 << 30))           # ullTotalPhys
    e.wr(a[0] + 16, struct.pack('<Q', 1 << 30))          # ullAvailPhys
    e.wr(a[0] + 24, struct.pack('<Q', 2 << 30))          # ullTotalPageFile
    e.wr(a[0] + 32, struct.pack('<Q', 2 << 30))
    e.wr(a[0] + 40, struct.pack('<Q', 0x7FFE0000))       # ullTotalVirtual
    e.wr(a[0] + 48, struct.pack('<Q', 0x7F000000))
    return 1
BATCH3 = {
 'GetProcessAffinityMask': (h_GetProcessAffinityMask, 'stdcall', 3),
 'SetProcessAffinityMask': (h_ret1, 'stdcall', 2),
 'SetThreadAffinityMask': (lambda e, a, x: 1, 'stdcall', 2),
 'GetCurrentProcessorNumber': (h_noop0, 'stdcall', 0),
 'SwitchToThread': (h_noop0, 'stdcall', 0),
 'GetNativeSystemInfo': (h_GetSystemInfo, 'stdcall', 1),
 'GlobalMemoryStatus': (h_GlobalMemoryStatusEx, 'stdcall', 1),
 'GlobalMemoryStatusEx': (h_GlobalMemoryStatusEx, 'stdcall', 1),
 'GetDiskFreeSpaceExA': (lambda e, a, x: (e.wr(a[1], struct.pack('<Q', 1 << 33)) if a[1] else 0,
                                          e.wr(a[2], struct.pack('<Q', 1 << 33)) if a[2] else 0, 1)[2], 'stdcall', 4),
 'GetDiskFreeSpaceA': (lambda e, a, x: (e.w32(a[1], 8) if a[1] else 0, e.w32(a[2], 512) if a[2] else 0,
                                        e.w32(a[3], 1 << 20) if a[3] else 0, e.w32(a[4], 1 << 21) if a[4] else 0, 1)[4], 'stdcall', 5),
}
HLE.update(BATCH3)

# ================================================================ batch 4
# The monkey's covert channel: Get/SetThreadContext with
# ContextFlags=0x10010 (CONTEXT_DEBUG_REGISTERS) pass pointers through
# Dr0..Dr7 (proven from the zlib-wrapper decompilation: pointers are
# stashed NOT/XOR-encoded across calls; Dr7 carries sentinels
# 0x11110455/0x11110400). The harness keeps the debug registers as
# per-thread state that persists between calls. GP fields are filled
# only if a caller ever asks for them.
def _dr(e):
    if not hasattr(e, 'dr'):
        e.dr = [0] * 8
    return e.dr
def h_GetThreadContext2(e, a, x):
    from unicorn.x86_const import (UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX,
        UC_X86_REG_EDX, UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP,
        UC_X86_REG_ESP, UC_X86_REG_EFLAGS)
    uc = e.uc; ctx = a[1]
    flags = e.r32(ctx)
    dr = _dr(e)
    for i, off in enumerate((0x04, 0x08, 0x0C, 0x10, 0x14, 0x18)):
        src = (dr[0], dr[1], dr[2], dr[3], dr[6], dr[7])[i]
        e.w32(ctx + off, src)
    if flags & 0x07:  # CONTROL/INTEGER/SEGMENTS requested: fill GP too
        w = lambda off, v: e.w32(ctx + off, v)
        w(0x9C, uc.reg_read(UC_X86_REG_EDI)); w(0xA0, uc.reg_read(UC_X86_REG_ESI))
        w(0xA4, uc.reg_read(UC_X86_REG_EBX)); w(0xA8, uc.reg_read(UC_X86_REG_EDX))
        w(0xAC, uc.reg_read(UC_X86_REG_ECX)); w(0xB0, uc.reg_read(UC_X86_REG_EAX))
        w(0xB4, uc.reg_read(UC_X86_REG_EBP))
        w(0xB8, getattr(e, '_cur_retaddr', 0))
        w(0xC0, uc.reg_read(UC_X86_REG_EFLAGS))
        w(0xC4, getattr(e, '_cur_esp', 0) + 4)
    return 1
def h_SetThreadContext2(e, a, x):
    flags = e.r32(a[1])
    if not hasattr(e, '_stc_flags'):
        e._stc_flags = set()
    if flags not in e._stc_flags:
        e._stc_flags.add(flags)
        log(f'  [hle] SetThreadContext flags={flags:#x}')
    if flags & 0x10010:  # CONTEXT_DEBUG_REGISTERS: only then do the
        # Dr fields in the caller's struct carry meaning. A GP-only Set
        # must not clobber the mailbox state with stale struct bytes.
        dr = _dr(e)
        vals = [e.r32(a[1] + off) for off in (0x04, 0x08, 0x0C, 0x10, 0x14, 0x18)]
        dr[0], dr[1], dr[2], dr[3], dr[6], dr[7] = vals
        log(f'  [hle] SetThreadContext Dr: {[hex(v) for v in vals]}')
    return 1
HLE['GetThreadContext'] = (h_GetThreadContext2, 'stdcall', 2)
HLE['SetThreadContext'] = (h_SetThreadContext2, 'stdcall', 2)

# ---- run69: implement msvcr71 _access (existence probe; the engine
# builds a path string and probes it before opening -- run68 stopped here)
def h_access(e, a, x):
    p = e.cstr(a[0])
    hp = host_path(p)
    ok = bool(hp and _os.path.exists(hp))
    _audit('_access', win=p, host=hp, mode=a[1], exists=ok)
    log(f'  [hle] _access({p!r}, mode={a[1]}) -> host={hp!r} exists={ok}')
    if ok: return 0
    e.last_error = 2
    if hasattr(e, '_errno_cell'): e.w32(e._errno_cell, 2)
    return -1
HLE['_access'] = (h_access, 'cdecl', 2)

# ---- run70: CRT string/misc batch (all pure, logged; none present in HLE)
def _wlen(e, a):
    n = 0
    while True:
        try:
            if e.r16(a + 2 * n) == 0: break
        except Exception: break
        n += 1
        if n > 65536: break
    return n
def h_wcslen(e, a, x):
    s = e.wstr(a[0])[:200]
    log(f'  [hle] wcslen({s!r})')
    return _wlen(e, a[0])
def h_wcsncpy(e, a, x):
    dst, s, n = a[0], a[1], a[2]
    raw = e.rd(s, 2 * min(_wlen(e, s), n)) if s else b''
    out = bytearray(raw)
    while len(out) < 2 * n: out += b'\x00\x00'
    e.wr(dst, bytes(out[:2 * n]))
    return dst
def h_wcscat(e, a, x):
    dst, s = a[0], a[1]
    dlen = _wlen(e, dst)
    raw = e.rd(s, 2 * _wlen(e, s)) if s else b''
    e.wr(dst + 2 * dlen, raw + b'\x00\x00')
    return dst
def h_strnicmp(e, a, x):
    s1 = e.cstr(a[0])[:a[2]] if a[0] else ''
    s2 = e.cstr(a[1])[:a[2]] if a[1] else ''
    l1, l2 = s1.lower(), s2.lower()
    if l1 == l2: return 0
    return -1 if l1 < l2 else 1
def h_strlwr(e, a, x):
    if a[0]:
        s = e.cstr(a[0])
        e.put_cstr(a[0], s.lower())
    return a[0]
def h_isprint(e, a, x):
    return 1 if 0x20 <= (a[0] & 0xFF) <= 0x7E else 0
def h_isxdigit(e, a, x):
    c = a[0] & 0xFF
    return 1 if (48 <= c <= 57 or 65 <= c <= 70 or 97 <= c <= 102) else 0
def h_swab(e, a, x):
    srcb, dst, n = a[0], a[1], a[2] & ~1
    raw = bytearray(e.rd(srcb, n)) if n else bytearray()
    for i in range(0, n, 2): raw[i], raw[i + 1] = raw[i + 1], raw[i]
    if n: e.wr(dst, bytes(raw))
    return None
def h_errno(e, a, x):
    if not hasattr(e, '_errno_cell'):
        e._errno_cell = e.alloc.alloc(4, 'errno')
        e.w32(e._errno_cell, 0)
    return e._errno_cell
HLE['wcslen'] = (h_wcslen, 'cdecl', 1)
HLE['wcsncpy'] = (h_wcsncpy, 'cdecl', 3)
HLE['wcscat'] = (h_wcscat, 'cdecl', 2)
HLE['_strnicmp'] = (h_strnicmp, 'cdecl', 3)
HLE['_strlwr'] = (h_strlwr, 'cdecl', 1)
HLE['isprint'] = (h_isprint, 'cdecl', 1)
HLE['isxdigit'] = (h_isxdigit, 'cdecl', 1)
HLE['_swab'] = (h_swab, 'cdecl', 3)
HLE['_chkesp'] = (lambda e, a, x: 0, 'cdecl', 0)
HLE['_resetstkoflw'] = (lambda e, a, x: 1, 'cdecl', 0)
HLE['_errno'] = (h_errno, 'cdecl', 0)

# ---- run71: swprintf (MSVC7.1-era: old-style (buffer, format, ...) is
# likely; new-style (buffer, count, format, ...) detected heuristically)
def _fmt_w(e, fmt, args):
    out = []
    ai = 0
    i = 0
    while i < len(fmt):
        c = fmt[i]
        if c != '%':
            out.append(c); i += 1; continue
        i += 1
        if i < len(fmt) and fmt[i] == '%':
            out.append('%'); i += 1; continue
        flags = ''
        while i < len(fmt) and fmt[i] in '-+ #0':
            flags += fmt[i]; i += 1
        width = ''
        while i < len(fmt) and fmt[i].isdigit():
            width += fmt[i]; i += 1
        prec = None
        if i < len(fmt) and fmt[i] == '.':
            i += 1; prec = ''
            while i < len(fmt) and fmt[i].isdigit():
                prec += fmt[i]; i += 1
        lng = ''
        while i < len(fmt) and fmt[i] in 'lhIw':
            lng += fmt[i]; i += 1
        if i >= len(fmt): break
        conv = fmt[i]; i += 1
        a = args[ai] if ai < len(args) else 0
        if conv in 'di':
            v = a - (1 << 32) if a >= (1 << 31) else a
            s = str(v); ai += 1
        elif conv == 'u':
            s = str(a); ai += 1
        elif conv in 'xX':
            s = format(a, 'x' if conv == 'x' else 'X'); ai += 1
            if '#' in flags: s = '0x' + s
        elif conv == 'o':
            s = format(a, 'o'); ai += 1
        elif conv == 'p':
            s = format(a, '08X'); ai += 1
        elif conv == 'c':
            s = chr(a & 0xFFFF); ai += 1
        elif conv == 'C':
            s = chr(a & 0xFF); ai += 1
        elif conv == 's':
            s = e.wstr(a); ai += 1
            if prec not in (None, ''): s = s[:int(prec)]
        elif conv == 'S':
            s = e.cstr(a); ai += 1
            if prec not in (None, ''): s = s[:int(prec)]
        elif conv in 'feEgG':
            lo = a; hi = args[ai + 1] if ai + 1 < len(args) else 0
            v = struct.unpack('<d', struct.pack('<II', lo, hi))[0]
            s = ('%g' % v) if conv in 'gG' else ('%f' % v)
            ai += 2
        else:
            s = '%' + conv
        w = int(width) if width else 0
        if w and len(s) < w:
            pad = ' ' * (w - len(s))
            s = s + pad if '-' in flags else pad + s
        out.append(s)
    return ''.join(out)
def h_swprintf(e, a, x):
    buf = a[0]
    # heuristic: old-style if a[1] reads as a plausible wide format string
    old_style = False
    try:
        f0 = e.wstr(a[1])
        old_style = ('%' in f0) or len(f0) < 4096
    except Exception:
        old_style = False
    if old_style:
        fmt, vargs, count = e.wstr(a[1]), [e.r32(getattr(e, '_cur_esp', 0) + 12 + 4 * i) for i in range(10)], None
        layout = 'old(buffer,format)'
    else:
        fmt, count = e.wstr(a[2]), a[1]
        vargs = [e.r32(getattr(e, '_cur_esp', 0) + 16 + 4 * i) for i in range(10)]
        layout = 'new(buffer,count,format)'
    s = _fmt_w(e, fmt, vargs)
    log(f'  [hle] swprintf {layout} fmt={fmt!r} -> {s!r}')
    if count is not None and len(s) >= count:
        e.wr(buf, s[:max(count - 1, 0)].encode('utf-16-le') + b'\x00\x00')
        return -1
    e.wr(buf, s.encode('utf-16-le') + b'\x00\x00')
    return len(s)
HLE['swprintf'] = (h_swprintf, 'cdecl', 4)

# ---- run72: std::exception lifetime no-ops (thiscall; return this)
def h_exc_ctor(e, a, x):
    log(f'  [hle] exception ctor this={x:#x} args={a[:2]}')
    return x
def h_exc_dtor(e, a, x):
    log(f'  [hle] exception dtor this={x:#x}')
    return x
HLE['??0exception@@QAE@XZ'] = (h_exc_ctor, 'thiscall', 0)
HLE['??0exception@@QAE@ABV0@@Z'] = (h_exc_ctor, 'thiscall', 1)
HLE['??1exception@@UAE@XZ'] = (h_exc_dtor, 'thiscall', 0)

# ---- run73: _stat (MSVC _stat32 layout, 36 bytes)
def h_stat(e, a, x):
    p = e.cstr(a[0]); hp = host_path(p)
    log(f'  [hle] _stat({p!r}) -> host={hp!r}')
    if not hp or not _os.path.exists(hp):
        _audit('_stat', win=p, host=hp, result='FAIL')
        e.last_error = 2
        if hasattr(e, '_errno_cell'): e.w32(e._errno_cell, 2)
        return -1
    st = _os.stat(hp)
    buf = a[1]
    if buf:
        isdir = _os.path.isdir(hp)
        mode = (0x4000 if isdir else 0x8000) | 0x1FF
        e.w32(buf + 0, 0)
        e.w32(buf + 4, 0)
        e.wr(buf + 8, struct.pack('<Hhhh', mode, 1, 0, 0))
        e.w32(buf + 16, 0)
        e.w32(buf + 20, int(st.st_size) & 0xFFFFFFFF)
        e.w32(buf + 24, int(st.st_atime))
        e.w32(buf + 28, int(st.st_mtime))
        e.w32(buf + 32, int(st.st_ctime))
    log(f'  [hle] _stat ok size={st.st_size}')
    return 0
HLE['_stat'] = (h_stat, 'cdecl', 2)

# ---- run74: CRT FILE* layer (Python files behind guest FILE* pointers)
def _crt_open(e, path, mode):
    hp = host_path(path)
    if hp is None:
        _audit('fopen', win=path, mode=mode, host=None, result='FAIL-noresolve')
        e.last_error = 2; return 0
    m = mode.replace('b', '').replace('t', '')
    py = {'r': 'rb', 'w': 'wb', 'a': 'ab', 'r+': 'r+b', 'w+': 'w+b', 'a+': 'a+b'}.get(m, 'rb')
    if py[0] in 'wa':
        try: _os.makedirs(_os.path.dirname(hp), exist_ok=True)
        except Exception: pass
    try:
        fh = open(hp, py)
    except OSError:
        _audit('fopen', win=path, mode=mode, host=hp, result='FAIL-oserror')
        e.last_error = 2
        if hasattr(e, '_errno_cell'): e.w32(e._errno_cell, 2)
        return 0
    fp = e.alloc.alloc(16, 'FILE*')
    if not hasattr(e, '_crt'): e._crt = {}
    e._crt[fp] = (fh, path)
    _audit('fopen', win=path, mode=mode, host=hp, result=f'fp={fp:#x}')
    return fp
def _crt_get(e, fp):
    return (getattr(e, '_crt', {}) or {}).get(fp)
def h_crt_fopen(e, a, x):
    p, m = e.cstr(a[0]), e.cstr(a[1])
    r = _crt_open(e, p, m)
    log(f'  [hle] fopen({p!r}, {m!r}) -> {r:#x}')
    return r
def h_crt_wfopen(e, a, x):
    p, m = e.wstr(a[0]), e.wstr(a[1])
    r = _crt_open(e, p, m)
    log(f'  [hle] _wfopen({p!r}, {m!r}) -> {r:#x}')
    return r
def h_crt_fclose(e, a, x):
    ent = _crt_get(e, a[0])
    if not ent: return -1
    try: ent[0].close()
    except Exception: pass
    del e._crt[a[0]]
    return 0
def h_crt_fread(e, a, x):
    ent = _crt_get(e, a[3])
    if not ent: return 0
    data = ent[0].read(a[1] * a[2])
    _audit('fread', win=ent[1], req=a[1] * a[2], got=len(data), md5=_md5(data) if data else None)
    if data: e.wr(a[0], data)
    log(f'  [hle] fread({a[1]}x{a[2]} from {ent[1]!r}) -> {len(data) // a[1] if a[1] else 0} items')
    return len(data) // a[1] if a[1] else 0
def h_crt_fwrite(e, a, x):
    ent = _crt_get(e, a[3])
    if not ent: return 0
    data = e.rd(a[0], a[1] * a[2])
    _audit('fwrite', win=ent[1], n=len(data), md5=_md5(data))
    ent[0].write(data); ent[0].flush()
    return len(data) // a[1] if a[1] else 0
def h_crt_fseek(e, a, x):
    ent = _crt_get(e, a[0])
    if not ent: return -1
    try: ent[0].seek(a[1], a[2]); return 0
    except OSError: return -1
def h_crt_ftell(e, a, x):
    ent = _crt_get(e, a[0])
    if not ent: return -1
    try: return ent[0].tell()
    except OSError: return -1
def h_crt_fgets(e, a, x):
    ent = _crt_get(e, a[2])
    if not ent: return 0
    line = ent[0].readline(a[1] - 1) if a[1] > 1 else b''
    if not line: return 0
    e.wr(a[0], line + b'\x00')
    return a[0]
def h_crt_fputs(e, a, x):
    ent = _crt_get(e, a[1])
    if not ent: return -1
    s = e.cstr(a[0])
    ent[0].write(s.encode('latin-1')); ent[0].flush()
    return 1
def h_crt_vfprintf(e, a, x):
    ent = _crt_get(e, a[0])
    if not ent: return -1
    va = a[2]; args = [e.r32(va + 4 * i) for i in range(10)]
    s = _fmt(e, e.cstr(a[1]), args)
    ent[0].write(s.encode('latin-1')); ent[0].flush()
    return len(s)
def h_crt_fprintf(e, a, x):
    ent = _crt_get(e, a[0])
    if not ent: return -1
    s = _fmt(e, e.cstr(a[1]), a[2:])
    ent[0].write(s.encode('latin-1')); ent[0].flush()
    return len(s)
def h_crt_fflush(e, a, x):
    if a[0] == 0:
        for fh, _ in (getattr(e, '_crt', {}) or {}).values():
            try: fh.flush()
            except Exception: pass
        return 0
    ent = _crt_get(e, a[0])
    if not ent: return -1
    try: ent[0].flush(); return 0
    except Exception: return -1
def h_crt_rewind(e, a, x):
    ent = _crt_get(e, a[0])
    if ent:
        try: ent[0].seek(0)
        except Exception: pass
    return 0
HLE['fopen'] = (h_crt_fopen, 'cdecl', 2)
HLE['_wfopen'] = (h_crt_wfopen, 'cdecl', 2)
HLE['fclose'] = (h_crt_fclose, 'cdecl', 1)
HLE['fread'] = (h_crt_fread, 'cdecl', 4)
HLE['fwrite'] = (h_crt_fwrite, 'cdecl', 4)
HLE['fseek'] = (h_crt_fseek, 'cdecl', 3)
HLE['ftell'] = (h_crt_ftell, 'cdecl', 1)
HLE['fgets'] = (h_crt_fgets, 'cdecl', 3)
HLE['fputs'] = (h_crt_fputs, 'cdecl', 2)
HLE['vfprintf'] = (h_crt_vfprintf, 'cdecl', 3)
HLE['fprintf'] = (h_crt_fprintf, 'cdecl', 3)
HLE['fflush'] = (h_crt_fflush, 'cdecl', 1)
HLE['rewind'] = (h_crt_rewind, 'cdecl', 1)

# ---- run75: CRT time family (struct tm = 9 ints, 36 bytes)
def _tm_buf(e):
    if not hasattr(e, '_tm_cell'):
        e._tm_cell = e.alloc.alloc(36, 'struct tm')
    return e._tm_cell
def _write_tm(e, cell, t):
    e.wr(cell, struct.pack('<9i', t.tm_sec, t.tm_min, t.tm_hour, t.tm_mday,
                           t.tm_mon, t.tm_year - 1900, t.tm_wday, t.tm_yday, t.tm_isdst))
def h_localtime(e, a, x):
    import time as _t
    v = e.r32(a[0]) if a[0] else 0
    t = _t.localtime(v)
    cell = _tm_buf(e); _write_tm(e, cell, t)
    log(f'  [hle] localtime({v}) -> {t.tm_year}-{t.tm_mon + 1}-{t.tm_mday} {t.tm_hour}:{t.tm_min}:{t.tm_sec}')
    return cell
def h_gmtime(e, a, x):
    import time as _t
    v = e.r32(a[0]) if a[0] else 0
    t = _t.gmtime(v)
    cell = _tm_buf(e); _write_tm(e, cell, t)
    return cell
def h_mktime(e, a, x):
    import time as _t
    vals = struct.unpack('<9i', e.rd(a[0], 36)) if a[0] else (0,) * 9
    tup = (vals[5] + 1900, vals[4] + 1, vals[3], vals[2], vals[1], vals[0], 0, 0, vals[8])
    try: return int(_t.mktime(tup))
    except Exception: return -1
def h_asctime(e, a, x):
    import time as _t
    if not hasattr(e, '_asctime_cell'):
        e._asctime_cell = e.alloc.alloc(26, 'asctime')
    vals = struct.unpack('<9i', e.rd(a[0], 36)) if a[0] else (0,) * 9
    wday = ('Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat')[vals[6] % 7]
    mon = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')[vals[4] % 12]
    s = '%s %s %2d %02d:%02d:%02d %04d\n' % (wday, mon, vals[3], vals[2], vals[1], vals[0], vals[5] + 1900)
    e.put_cstr(e._asctime_cell, s)
    return e._asctime_cell
HLE['localtime'] = (h_localtime, 'cdecl', 1)
HLE['gmtime'] = (h_gmtime, 'cdecl', 1)
HLE['mktime'] = (h_mktime, 'cdecl', 1)
HLE['asctime'] = (h_asctime, 'cdecl', 1)

# ---- run77: FlushInstructionCache (no-op TRUE on x86) + full trace dump
def h_flush_icache(e, a, x):
    log(f'  [hle] FlushInstructionCache(proc={a[0]:#x}, base={a[1]:#x}, size={a[2]:#x}) -> 1')
    return 1
HLE['FlushInstructionCache'] = (h_flush_icache, 'stdcall', 3)

# ---- run80: _set_se_translator (CRT: install SE->C++ translator, return previous)
def h_set_se_translator(e, a, x):
    log(f'  [hle] _set_se_translator(new={a[0]:#x}) -> 0 (no previous)')
    return 0
for _k in ('?_set_se_translator@@YAP6AXIPAU_EXCEPTION_POINTERS@@@ZP6AXI0@Z@Z',
           'msvcr71.dll!?_set_se_translator@@YAP6AXIPAU_EXCEPTION_POINTERS@@@ZP6AXI0@Z@Z',
           '_set_se_translator'):
    HLE[_k] = (h_set_se_translator, 'cdecl', 1)  # run85: @@YA=cdecl, not stdcall


# ================================================================ batch 5 (run152)
# MSVCP71 ostringstream fake + basic_string ctor(ptr,n) + small stubs for
# pfcom.dll's unresolved imports. ostringstream state lives Python-side,
# keyed by the guest `this`; str() materializes a real guest std::string
# via the proven _sinit/_sset helpers above.
_OSTR = {}
def _oss_ctor(e, a, x):
    _OSTR[x] = bytearray()
    try:
        _h = e.halt_stub(); e.w32(x, _h); e.w32(x + 4, _h)
    except Exception:
        pass
    return x
def _oss_dtor(e, a, x):
    _OSTR.pop(x, None); return 0
def _oss_puts(e, a, x):
    _OSTR.setdefault(a[0], bytearray()).extend(e.cstr(a[1]).encode('latin-1'))
    return a[0]
def _oss_puti(e, a, x):
    _v = a[0] - 0x100000000 if a[0] & 0x80000000 else a[0]
    _OSTR.setdefault(x, bytearray()).extend(str(_v).encode('latin-1'))
    return x
def _oss_str(e, a, x):
    _sinit(e, a[0], 1)
    _sset(e, a[0], bytes(_OSTR.get(x, b'')).decode('latin-1'), 1)
    return a[0]
HLE['??0?$basic_ostringstream@DU?$char_traits@D@std@@V?$allocator@D@2@@std@@QAE@H@Z'] = (_oss_ctor, 'thiscall', 1)
HLE['??_D?$basic_ostringstream@DU?$char_traits@D@std@@V?$allocator@D@2@@std@@QAEXXZ'] = (_oss_dtor, 'thiscall', 0)
HLE['??$?6U?$char_traits@D@std@@@std@@YAAAV?$basic_ostream@DU?$char_traits@D@std@@@0@AAV10@PBD@Z'] = (_oss_puts, 'cdecl', 2)
HLE['??6?$basic_ostream@DU?$char_traits@D@std@@@std@@QAEAAV01@H@Z'] = (_oss_puti, 'thiscall', 1)
HLE['?str@?$basic_ostringstream@DU?$char_traits@D@std@@V?$allocator@D@2@@std@@QBE?AV?$basic_string@DU?$char_traits@D@std@@V?$allocator@D@2@@2@XZ'] = (_oss_str, 'thiscall', 1)
def _ctor_n1(e, a, x):
    _sinit(e, x, 1); _sset(e, x, (e.cstr(a[0]) if a[0] else '')[:a[1]], 1); return x
def _ctor_n2(e, a, x):
    _sinit(e, x, 2); _sset(e, x, (e.wstr(a[0]) if a[0] else '')[:a[1]], 2); return x
HLE['??0?$basic_string@DU?$char_traits@D@std@@V?$allocator@D@2@@std@@QAE@PBDI@Z'] = (_ctor_n1, 'thiscall', 2)
HLE['??0?$basic_string@GU?$char_traits@G@std@@V?$allocator@G@2@@std@@QAE@PBDI@Z'] = (_ctor_n2, 'thiscall', 2)
def h_lstrcpynA(e, a, x):
    s = e.cstr(a[1])[:max(a[2] - 1, 0)] if a[2] else ''
    e.put_cstr(a[0], s); return a[0]
def h_wcscpy128(e, a, x):
    s = e.wstr(a[1]); e.wr(a[0], s.encode('utf-16-le') + b'\x00\x00'); return a[0]
def h_wcsicmp128(e, a, x):
    s1 = e.wstr(a[0]).lower(); s2 = e.wstr(a[1]).lower()
    return (s1 > s2) - (s1 < s2)
def h_wcsnicmp128(e, a, x):
    s1 = e.wstr(a[0])[:a[2]].lower(); s2 = e.wstr(a[1])[:a[2]].lower()
    return (s1 > s2) - (s1 < s2)
def h_isalnum128(e, a, x):
    c = a[0] & 0xFF
    return 1 if c < 128 and chr(c).isalnum() else 0
_CTIME_BUF = [0]
def h_ctime128(e, a, x):
    if not _CTIME_BUF[0]:
        _CTIME_BUF[0] = e.alloc.alloc(32, 'ctime buf')
        e.put_cstr(_CTIME_BUF[0], 'Thu Jan  1 00:00:00 1970\n')
    return _CTIME_BUF[0]
def h_CoTaskMemRealloc128(e, a, x):
    return e.alloc.realloc(a[0], a[1]) if a[0] else e.alloc.alloc(a[1], 'CoTaskMem')
HLE['DisableThreadLibraryCalls'] = (h_ret1, 'stdcall', 1)
HLE['IsDBCSLeadByte'] = (h_noop0, 'stdcall', 1)
HLE['lstrcpynA'] = (h_lstrcpynA, 'stdcall', 3)
HLE['CharNextA'] = ((lambda e, a, x: a[0] + 1 if a[0] else 0), 'stdcall', 1)
def h_RegInfoStub150(e, a, x):
    _audit('RegQueryInfoKeyA', handle=hex(a[0]), result=2)
    log('  [hle] RegQueryInfoKeyA -> 2 (stub, unchanged from 146)')
    return 2
def h_RegEnumStub150(e, a, x):
    _audit('RegEnumKeyExA', handle=hex(a[0]), result=2)
    log('  [hle] RegEnumKeyExA -> 2 (stub, unchanged from 146)')
    return 2
HLE['RegQueryInfoKeyA'] = (h_RegInfoStub150, 'stdcall', 12)
HLE['RegEnumKeyExA'] = (h_RegEnumStub150, 'stdcall', 8)
HLE['CoTaskMemRealloc'] = (h_CoTaskMemRealloc128, 'stdcall', 2)
HLE['wcscpy'] = (h_wcscpy128, 'cdecl', 2)
HLE['_wcsicmp'] = (h_wcsicmp128, 'cdecl', 2)
HLE['_wcsnicmp'] = (h_wcsnicmp128, 'cdecl', 3)
HLE['isalnum'] = (h_isalnum128, 'cdecl', 1)
HLE['ctime'] = (h_ctime128, 'cdecl', 1)
HLE['vprintf'] = (h_noop0, 'cdecl', 2)

if __name__ == '__main__':
    main()
