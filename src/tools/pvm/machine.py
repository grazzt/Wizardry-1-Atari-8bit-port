"""Host-side Apple Pascal 1.1 p-machine for running WIZARDRY.CODE.

Design:
- One 64K byte memory, as on the Apple. Frames, loaded code segments and the
  heap live in it, so p-code pointer arithmetic, MOVELEFT, UNITREAD into
  arrays and absolute addresses (the game uses $2000 and $4000) all work.
- The evaluation stack is a Python list. Its depth still counts against the
  memory stack when measuring high-water marks.
- Code segments are loaded onto the stack when first called and released
  when their last activation returns, as on the real machine.
- Native procedures run in a 6502 emulator on the same memory, with the
  p-machine evaluation stack copied to and from the 6502 hardware stack, as
  on the Apple, where the two are the same.
- The Pascal OS is not run. The OS entry points the game uses (WRITE, READ,
  GOTOXY, CONCAT, COPY, ...) and the standard procedures are implemented in
  Python; the game's p-code reaches only the INPUT/OUTPUT globals of the OS.

Frame layout: the caller pushes arguments (and, for a function, two result
words last). Local word 1 is the last word pushed; arguments occupy the low
offsets and locals follow. Word n of a frame is at base + 2*(n - 1).
"""
from dataclasses import dataclass, field
import random

from ucsd import m6502, pcode
from ucsd.codefile import CodeFile
from .console import Console, InputExhausted
from .cpu6502 import CPU6502
from . import patches

MSCW_BYTES = 12           # mark-stack control word size counted per frame
TRAP_RETURN = 0xFFF0      # RTS target that ends a native call
BIOS_CONCK = 0xBF0A       # keyboard poll called by KEYAVAIL and MVCURSOR(80)
BIOS_RPTR, BIOS_WPTR = 0xBF18, 0xBF19

EXEC_ERRORS = {
    0: 'system error', 1: 'invalid index', 2: 'no segment', 3: 'exit from uncalled procedure',
    4: 'stack overflow', 5: 'integer overflow', 6: 'divide by zero', 7: 'NIL pointer',
    8: 'program interrupted', 9: 'system I/O error', 10: 'user I/O error',
    11: 'unimplemented instruction', 12: 'floating point error', 13: 'string overflow',
    14: 'halt', 15: 'breakpoint',
}




CHAINSTUFF = 28          # SYSTEM.LIBRARY unit used by SYSTEM.STARTUP
RESTARTABLE = {'CXP', 'CSP', 'CGP', 'CLP', 'CIP', 'CBP'}
MVCURSOR = (1, 31)        # MVCURSOR(80, y) waits for a key, stirring the RNG


class VMError(RuntimeError):
    def __init__(self, code, detail=''):
        self.code = code
        super().__init__(f'execution error {code} ({EXEC_ERRORS.get(code, "?")}){": " + detail if detail else ""}')


class Halted(Exception):
    pass


def s16(v):
    return v - 0x10000 if v & 0x8000 else v


@dataclass
class Segment:
    number: int
    name: str
    code: bytes
    procedures: dict
    base: int = 0
    refs: int = 0
    permanent: bool = False
    decoded: dict = field(default_factory=dict)


@dataclass
class Frame:
    seg: Segment
    proc: object
    base: int            # address of local word 1
    size: int            # bytes of parameters + locals
    static: 'Frame'
    dynamic: 'Frame'
    ret_seg: Segment
    ret_ipc: int
    lex: int

    def addr(self, offset):
        return (self.base + 2 * (offset - 1)) & 0xFFFF


# SYSTEM.STARTUP's utilities segment and its disk-swap prompts (see _swap_disks).
UTILS, EXITUTIL, RDSCNTOC = 7, 7, 9

class DiskUnit:
    """A writable block device backed by a 140K image (DOS sector order)."""

    def __init__(self, disk):
        self.disk = disk
        self.image = bytearray(disk.image)

    def _sectors(self, block):
        track, index = divmod(block, 8)
        if self.disk.order == 'prodos':
            return [(block * 2), (block * 2 + 1)]
        a, b = m_dos_order[index]
        return [track * 16 + a, track * 16 + b]

    def read(self, block, count):
        out = bytearray()
        while len(out) < count:
            for sector in self._sectors(block):
                out += self.image[sector * 256:(sector + 1) * 256]
            block += 1
        return bytes(out[:count])

    def write(self, block, data):
        data = bytes(data) + bytes(-len(data) % 512)
        for i in range(0, len(data), 512):
            for half, sector in enumerate(self._sectors(block + i // 512)):
                self.image[sector * 256:(sector + 1) * 256] = data[i + half * 256:i + half * 256 + 256]


m_dos_order = [(0, 14), (13, 12), (11, 10), (9, 8), (7, 6), (5, 4), (3, 2), (1, 15)]


class PMachine:
    def __init__(self, codefile: CodeFile, units: dict, console: Console = None, *,
                 stack_top=0x9200, heap_start=0x4000, key_seed=1, key_polls=(50, 3000),
                 startup: CodeFile = None, names=None, trace=None):
        """Run `codefile` (WIZARDRY.CODE), or first `startup` (SYSTEM.STARTUP),
        which chains to it. Unit 4 is drive 1: the boot disk (unit 5,
        write-protected) while the startup program runs, then the scenario disk."""
        self.mem = bytearray(0x10000)
        self.units = units
        self.console = console or Console()
        self.names = names or {}
        self.trace = trace
        self.stack_top = stack_top
        self.heap_start = heap_start
        self.io_result = 0
        self.eoln = False
        self.instructions = 0
        self.native_calls = 0
        self.low_water = stack_top          # lowest memory-stack address reached
        self.heap_high = heap_start
        self.segment_loads = {}
        self.display = {'graphics': False, 'mixed': False, 'hires': False}
        self.files = {}                     # FIB address -> directory entry
        self.key_seen = False               # a $C000 read reported a key

        # Key timing: the game spins incrementing its RNG until a key arrives,
        # so the number of polls per key is what seeds the game's randomness.
        self.key_rng = random.Random(key_seed)
        self.key_polls = key_polls
        self.polls_left = None
        self.poll_log = {}            # key index -> polls before it (for lockstep tests)

        self.cpu = CPU6502(self.mem, self._io_read, self._io_write)
        self.cpu.traps[BIOS_CONCK] = self._bios_conck

        self.game = patches.apply(codefile, 'WIZARDRY.CODE')
        if startup is not None:
            self.drive1, self.drive1_readonly = units[5], True
            self._start_program(patches.apply(startup, 'SYSTEM.STARTUP'))
        else:
            self.drive1, self.drive1_readonly = units[4], False
            self._start_program(self.game)

    def _start_program(self, codefile):
        """Set up the p-machine for a code file and enter its program body."""
        self.codefile = codefile
        self.program = 'SYSTEM.STARTUP' if codefile is not getattr(self, 'game', None) else 'WIZARDRY.CODE'
        self.segments = {s.number: s for s in codefile.segments}
        self.loaded = {}
        self.stack = []
        self.sp = self.stack_top
        self.heap_top = self.heap_start
        self.chain = None
        self.frame = None
        # Pascal OS globals the program reaches: word 2 = INPUT, word 3 = OUTPUT.
        self.input_fib, self.output_fib = self._alloc(2), self._alloc(2)
        os_frame = self._alloc(8)
        self.os = Frame(None, None, os_frame, 8, None, None, None, 0, -1)
        self.store(self.os.addr(2), self.input_fib)
        self.store(self.os.addr(3), self.output_fib)

        main = self._load(1)
        main.permanent = True
        proc = main.procedures[1]
        self.base = self._new_frame(main, proc, [0] * (proc.param_bytes // 2), self.os, None, None, 0)
        self.frame, self.seg, self.ipc = self.base, main, proc.enter
        self.running = True

    # -- memory ---------------------------------------------------------------
    def load(self, addr):
        return self.mem[addr] | self.mem[(addr + 1) & 0xFFFF] << 8

    def store(self, addr, value):
        self.mem[addr] = value & 0xFF
        self.mem[(addr + 1) & 0xFFFF] = (value >> 8) & 0xFF

    def push(self, value):
        self.stack.append(value & 0xFFFF)

    def pop(self):
        return self.stack.pop()

    def _alloc(self, size):
        self.sp -= size
        self._check_stack()
        return self.sp

    def _check_stack(self):
        effective = self.sp - 2 * len(self.stack)
        if effective < self.low_water:
            self.low_water = effective
        if effective <= self.heap_top:
            raise VMError(4, f'stack {effective:#06x} met heap {self.heap_top:#06x}')

    def pstring(self, addr):
        return self.mem[addr + 1:addr + 1 + self.mem[addr]].decode('latin1')

    # -- segments and frames --------------------------------------------------
    def _load(self, number):
        if number in self.loaded:
            return self.loaded[number]
        if number not in self.segments:
            raise VMError(2, f'segment {number}')
        src = self.segments[number]
        seg = Segment(number, src.name, src.code, {p.number: p for p in src.procedures})
        seg.base = self._alloc(len(src.code))
        self.mem[seg.base:seg.base + len(src.code)] = src.code
        for proc in src.procedures:
            if proc.native:
                self._relocate(seg, proc)
        self.loaded[number] = seg
        self.segment_loads[seg.name] = self.segment_loads.get(seg.name, 0) + 1
        return seg

    def _relocate(self, seg, proc):
        _, lists = m6502.native_layout(seg.code, proc)
        base_rel, seg_rel, proc_rel, interp_rel = lists
        if base_rel or interp_rel:
            raise VMError(0, f'{seg.name}.{proc.number}: base/interpreter relocation not supported')
        for offset, delta in [(r, seg.base) for r in seg_rel] + [(r, seg.base + proc.enter) for r in proc_rel]:
            addr = seg.base + offset
            self.store(addr, self.load(addr) + delta)

    def _release(self, seg):
        seg.refs -= 1
        if seg.refs == 0 and not seg.permanent:
            if self.sp != seg.base:
                raise VMError(0, f'segment {seg.name} is not on top of the stack')
            self.sp += len(seg.code)
            del self.loaded[seg.number]

    def _new_frame(self, seg, proc, args, static, ret_seg, ret_ipc, lex):
        size = proc.param_bytes + proc.data_bytes
        self.sp -= size + MSCW_BYTES
        self._check_stack()
        base = self.sp + MSCW_BYTES
        for i, value in enumerate(args):
            self.store(base + 2 * i, value)
        frame = Frame(seg, proc, base, size, static, self.frame if ret_seg else None, ret_seg, ret_ipc, lex)
        seg.refs += 1
        return frame

    def call(self, seg_number, proc_number):
        src = self.segments.get(seg_number)
        if src is None:
            raise VMError(2, f'segment {seg_number}')
        proc = next((p for p in src.procedures if p.number == proc_number), None)
        if proc is None:
            raise VMError(0, f'no procedure {seg_number}.{proc_number}')
        if self.program == 'SYSTEM.STARTUP' and seg_number == UTILS:
            self._swap_disks(proc_number)
        seg = self._load(seg_number)
        if proc.native:
            self._call_native(seg, proc)
            return
        static = self.frame
        while static.lex > proc.lex_level - 1:
            static = static.static
        args = [self.pop() for _ in range(proc.param_bytes // 2)]
        frame = self._new_frame(seg, proc, args, static, self.seg, self.ipc, proc.lex_level)
        self._log('call', seg_number, proc_number)
        self.frame, self.seg, self.ipc = frame, seg, proc.enter

    def _swap_disks(self, proc_number):
        """The utilities ask the player to swap disks in drive 1: RDSCNTOC
        ("PLACE SCENARIO IN DRIVE 1") and EXITUTIL ("PLACE BOOT DISK IN DRIVE
        1"). With both disks at hand, swap as each procedure starts."""
        if proc_number == RDSCNTOC:
            self.drive1, self.drive1_readonly = self.units[4], False
        elif proc_number == EXITUTIL:
            self.drive1, self.drive1_readonly = self.units[5], True

    def ret(self, words):
        f = self.frame
        results = [self.load(f.addr(k)) for k in range(1, words + 1)]
        self.sp = f.base - MSCW_BYTES + f.size + MSCW_BYTES
        self._release(f.seg)
        if f.dynamic is None:
            if self.chain == 'WIZARDRY' and self.program == 'SYSTEM.STARTUP':
                # The OS runs the chained program; the player has been asked to
                # put the scenario disk in drive 1.
                self.drive1, self.drive1_readonly = self.units[4], False
                self._start_program(self.game)
            else:
                self.running = False
            return
        self.frame, self.seg, self.ipc = f.dynamic, f.ret_seg, f.ret_ipc
        for value in reversed(results):
            self.push(value)

    def exit_proc(self, seg_number, proc_number):
        """EXIT(proc): make every activation up to the named one run its exit code."""
        chain, f = [], self.frame
        while f is not None and f.proc is not None:
            chain.append(f)
            if f.seg.number == seg_number and f.proc.number == proc_number:
                break
            f = f.dynamic
        else:
            raise VMError(3, f'{seg_number}.{proc_number}')
        self.ipc = chain[0].proc.exit
        for callee, caller in zip(chain, chain[1:]):
            callee.ret_ipc = caller.proc.exit

    def _log(self, kind, seg, proc):
        if self.trace:
            depth = 0
            f = self.frame
            while f and f.proc:
                depth, f = depth + 1, f.dynamic
            self.trace(f'{"  " * depth}{kind} {self.name(seg, proc)}')

    def name(self, seg, proc):
        return self.names.get((seg, proc), f'{self.segments[seg].name}.{proc}')

    # -- native code ------------------------------------------------------------
    def _call_native(self, seg, proc):
        """Run a native routine with the evaluation stack on the 6502 stack."""
        if (seg.number, proc.number) == MVCURSOR and self.stack[-2] == 80 \
                and not self.console.key_available():
            raise InputExhausted()            # stop before the wait stirs the RNG
        self.native_calls += 1
        cpu = self.cpu
        depth = min(len(self.stack), 100)
        moved = self.stack[len(self.stack) - depth:]
        del self.stack[len(self.stack) - depth:]
        cpu.s = 0xFF
        for value in moved:                  # low byte ends nearer the top
            cpu.push(value >> 8)
            cpu.push(value)
        cpu.push((TRAP_RETURN - 1) >> 8)
        cpu.push(TRAP_RETURN - 1)
        self._log('native', seg.number, proc.number)
        cpu.run(seg.base + proc.enter, TRAP_RETURN)
        returned = []
        while cpu.s < 0xFF:                  # pulled top-first
            lo = cpu.pull()
            returned.append(lo | cpu.pull() << 8)
        self.stack.extend(reversed(returned))

    def _io_read(self, addr):
        if addr == 0xC000:                    # keyboard data, bit 7 = key waiting
            if not self.console.key_available():
                raise InputExhausted()
            if self.polls_left is None:
                self.polls_left = self.key_rng.randint(*self.key_polls)
                self.poll_log[self.console.keys_read] = self.polls_left
            if self.polls_left > 0:
                self.polls_left -= 1
                return 0
            return 0x80 | self.console.keys[0].encode('latin1')[0]
        self._soft_switch(addr)
        return 0

    def _io_write(self, addr, value):
        self._soft_switch(addr)

    def _soft_switch(self, addr):
        switches = {0xC050: ('graphics', True), 0xC051: ('graphics', False),
                    0xC052: ('mixed', False), 0xC053: ('mixed', True),
                    0xC056: ('hires', False), 0xC057: ('hires', True)}
        if addr in switches:
            key, value = switches[addr]
            self.display[key] = value

    def _bios_conck(self, cpu):
        """CONCK: the type-ahead buffer is empty unless a key has been 'typed'."""
        self.mem[BIOS_RPTR] = 0
        self.mem[BIOS_WPTR] = 0

    # -- main loop ----------------------------------------------------------------
    def fetch(self):
        seg, ipc = self.seg, self.ipc
        ins = seg.decoded.get(ipc)
        if ins is None:
            ins = pcode.decode(seg.code, ipc, self.frame.proc.jtab)
            seg.decoded[ipc] = ins
        return ins

    def run(self, max_instructions=None):
        """Run until the program ends, input runs out, or the limit is reached."""
        limit = None if max_instructions is None else self.instructions + max_instructions
        while self.running:
            if limit is not None and self.instructions >= limit:
                return 'limit'
            try:
                self.step()
            except InputExhausted:
                return 'input'
            except Halted:
                return 'halt'
        return 'end'

    def send(self, keys, max_instructions=50_000_000):
        """Type `keys` and run until the program needs more input."""
        self.console.keys.extend(keys)
        return self.run(max_instructions)

    def loaded_names(self):
        return [s.name for s in self.loaded.values()]

    def step(self):
        ins = self.fetch()
        self.instructions += 1
        self.ipc = ins.offset + ins.length
        op = ins.mnemonic
        handler = getattr(self, 'op_' + op, None)
        if op in RESTARTABLE:
            # Calls can stop for input midway (a native waiting for a key, an
            # OS READ). Undo the instruction so it reruns when keys arrive.
            saved = list(self.stack)
            try:
                handler(ins)
            except InputExhausted:
                self.stack = saved
                self.ipc = ins.offset
                self.instructions -= 1
                raise
        elif handler is not None:
            handler(ins)
        elif op == 'SLDC':
            self.push(ins.operands[0])
        elif op.startswith('SLDL'):
            self.push(self.load(self.frame.addr(int(op[4:]))))
        elif op.startswith('SLDO'):
            self.push(self.load(self.base.addr(int(op[4:]))))
        elif op.startswith('SIND'):
            self.push(self.load((self.pop() + 2 * int(op[4:])) & 0xFFFF))
        else:
            raise VMError(11, f'{op} at {self.seg.name}+{ins.offset:#06x}')

    # -- loads, stores, addresses ---------------------------------------------------
    def _level(self, levels):
        f = self.frame
        for _ in range(levels):
            f = f.static
        return f

    def op_LDCI(self, i): self.push(i.operands[0])
    def op_LDCN(self, i): self.push(0)
    def op_LDL(self, i): self.push(self.load(self.frame.addr(i.operands[0])))
    def op_LLA(self, i): self.push(self.frame.addr(i.operands[0]))
    def op_STL(self, i): self.store(self.frame.addr(i.operands[0]), self.pop())
    def op_LDO(self, i): self.push(self.load(self.base.addr(i.operands[0])))
    def op_LAO(self, i): self.push(self.base.addr(i.operands[0]))
    def op_SRO(self, i): self.store(self.base.addr(i.operands[0]), self.pop())
    def op_LOD(self, i): self.push(self.load(self._level(i.operands[0]).addr(i.operands[1])))
    def op_LDA(self, i): self.push(self._level(i.operands[0]).addr(i.operands[1]))
    def op_STR(self, i): self.store(self._level(i.operands[0]).addr(i.operands[1]), self.pop())
    def op_LSA(self, i): self.push(self.seg.base + i.offset + 1)
    def op_LPA(self, i): self.push(self.seg.base + i.offset + 2)

    def op_STO(self, i):
        value = self.pop()
        self.store(self.pop(), value)

    def op_IND(self, i): self.push(self.load((self.pop() + 2 * i.operands[0]) & 0xFFFF))
    def op_INC(self, i): self.push(self.pop() + 2 * i.operands[0])

    def op_IXA(self, i):
        index = s16(self.pop())
        self.push(self.pop() + 2 * i.operands[0] * index)

    def op_IXP(self, i):
        per_word, width = i.operands
        index = self.pop()
        addr = self.pop()
        self.push(addr + 2 * (index // per_word))
        self.push(width)
        self.push((index % per_word) * width)

    def op_LDP(self, i):
        right, width, addr = self.pop(), self.pop(), self.pop()
        self.push((self.load(addr) >> right) & ((1 << width) - 1))

    def op_STP(self, i):
        value, right, width, addr = self.pop(), self.pop(), self.pop(), self.pop()
        mask = ((1 << width) - 1) << right
        self.store(addr, (self.load(addr) & ~mask) | ((value << right) & mask))

    def op_LDB(self, i):
        addr = (self.stack[-2] + s16(self.stack[-1])) & 0xFFFF
        if 0xC000 <= addr <= 0xC0FF:          # p-code reading Apple I/O (the title's KEYPRESS)
            if addr == 0xC000 and not self.console.key_available():
                raise InputExhausted()        # nothing popped: rerun when keys arrive
            self.pop(), self.pop()
            value = self._io_read(addr)
            if addr == 0xC000 and value & 0x80:
                self.key_seen = True
            self.push(value)
            return
        self.pop(), self.pop()
        self.push(self.mem[addr])

    def op_STB(self, i):
        value, index = self.pop(), s16(self.pop())
        addr = (self.pop() + index) & 0xFFFF
        if 0xC000 <= addr <= 0xC0FF:          # p-code poking Apple soft switches
            self._soft_switch(addr)
            return
        self.mem[addr] = value & 0xFF

    def op_LDM(self, i):
        addr = self.pop()
        for k in reversed(range(i.operands[0])):
            self.push(self.load(addr + 2 * k))

    def op_STM(self, i):
        words = [self.pop() for _ in range(i.operands[0])]
        addr = self.pop()
        for k, value in enumerate(words):
            self.store(addr + 2 * k, value)

    def op_MOV(self, i):
        src, dst = self.pop(), self.pop()
        n = 2 * i.operands[0]
        self.mem[dst:dst + n] = self.mem[src:src + n]

    def op_SAS(self, i):
        src, dst = self.pop(), self.pop()
        if src < 256:                         # a character, not an address
            self.mem[dst], self.mem[dst + 1] = 1, src
            return
        n = self.mem[src]
        if n > i.operands[0]:
            raise VMError(13, f'{n} > {i.operands[0]}')
        self.mem[dst:dst + n + 1] = self.mem[src:src + n + 1]

    # -- arithmetic and logic -------------------------------------------------------
    def _binary(self, fn):
        b, a = s16(self.pop()), s16(self.pop())
        self.push(fn(a, b))

    def op_ADI(self, i): self._binary(lambda a, b: a + b)
    def op_SBI(self, i): self._binary(lambda a, b: a - b)
    def op_MPI(self, i): self._binary(lambda a, b: a * b)
    def op_LAND(self, i): self._binary(lambda a, b: a & b)
    def op_LOR(self, i): self._binary(lambda a, b: a | b)

    def op_DVI(self, i):
        b, a = s16(self.pop()), s16(self.pop())
        if b == 0:
            raise VMError(6)
        q = abs(a) // abs(b)
        self.push(q if (a < 0) == (b < 0) else -q)

    def op_MODI(self, i):
        b, a = s16(self.pop()), s16(self.pop())
        if b == 0:
            raise VMError(6)
        r = abs(a) % abs(b)
        self.push(-r if a < 0 else r)

    def op_ABI(self, i): self.push(abs(s16(self.pop())))
    def op_NGI(self, i): self.push(-s16(self.pop()))
    def op_SQI(self, i): self.push(s16(self.pop()) ** 2)
    def op_LNOT(self, i): self.push(~self.pop())

    def op_CHK(self, i):
        high, low = s16(self.pop()), s16(self.pop())
        value = s16(self.stack[-1])
        if not low <= value <= high:
            raise VMError(1, f'{value} not in {low}..{high}')

    def _compare_ints(self, fn):
        b, a = s16(self.pop()), s16(self.pop())
        self.push(int(fn(a, b)))

    def op_EQUI(self, i): self._compare_ints(lambda a, b: a == b)
    def op_NEQI(self, i): self._compare_ints(lambda a, b: a != b)
    def op_LESI(self, i): self._compare_ints(lambda a, b: a < b)
    def op_LEQI(self, i): self._compare_ints(lambda a, b: a <= b)
    def op_GRTI(self, i): self._compare_ints(lambda a, b: a > b)
    def op_GEQI(self, i): self._compare_ints(lambda a, b: a >= b)

    def _compare(self, i, fn):
        kind = i.operands[0]
        b, a = self.pop(), self.pop()
        if kind == 4:          # strings, by address (a char value is a 1-char string)
            sa = chr(a) if a < 256 else self.pstring(a)
            sb = chr(b) if b < 256 else self.pstring(b)
            result = fn((sa > sb) - (sa < sb))
        elif kind == 6:        # booleans
            result = fn((a & 1) - (b & 1))
        elif kind in (10, 12):  # byte arrays / multi-word blocks, by address
            n = i.operands[1] * (2 if kind == 12 else 1)
            ba, bb = bytes(self.mem[a:a + n]), bytes(self.mem[b:b + n])
            if kind == 12 and i.mnemonic not in ('EQU', 'NEQ'):
                raise VMError(11, f'{i.mnemonic} on words')
            result = fn((ba > bb) - (ba < bb))
        else:
            raise VMError(11, f'{i.mnemonic} type {kind}')
        self.push(int(result))

    def op_EQU(self, i): self._compare(i, lambda c: c == 0)
    def op_NEQ(self, i): self._compare(i, lambda c: c != 0)
    def op_LES(self, i): self._compare(i, lambda c: c < 0)
    def op_LEQ(self, i): self._compare(i, lambda c: c <= 0)
    def op_GRT(self, i): self._compare(i, lambda c: c > 0)
    def op_GEQ(self, i): self._compare(i, lambda c: c >= 0)

    # -- control ----------------------------------------------------------------------
    def op_UJP(self, i): self.ipc = i.targets[0]
    def op_NOP(self, i): pass

    def op_FJP(self, i):
        if not self.pop() & 1:
            self.ipc = i.targets[0]

    def op_XJP(self, i):
        low, high, default, cases = i.operands
        index = s16(self.pop())
        self.ipc = cases[index - low] if low <= index <= high else default

    def op_CXP(self, i):
        seg, proc = i.operands
        if seg == 0:
            self.call_os(proc)
        elif seg == CHAINSTUFF and seg not in self.segments:
            self.call_chainstuff(proc)
        else:
            self.call(seg, proc)

    def call_chainstuff(self, n):
        """The CHAINSTUFF library unit: SYSTEM.STARTUP sets the program to run next."""
        if n == 1:                            # unit initialisation
            return
        if n == 2:                            # SETCHAIN(name)
            self.chain = self.pstring(self.pop())
            return
        raise VMError(11, f'CHAINSTUFF procedure {n}')
    def op_CLP(self, i): self.call(self.seg.number, i.operands[0])
    def op_CGP(self, i): self.call(self.seg.number, i.operands[0])
    def op_CIP(self, i): self.call(self.seg.number, i.operands[0])
    def op_CBP(self, i): self.call(self.seg.number, i.operands[0])
    def op_RNP(self, i): self.ret(i.operands[0])
    def op_RBP(self, i): self.ret(i.operands[0])

    def op_XIT(self, i):
        raise Halted()

    def op_BPT(self, i):
        pass

    # -- standard procedures (CSP) ----------------------------------------------------
    def op_CSP(self, i):
        n = i.operands[0]
        if n in (2, 3):                       # MOVELEFT / MOVERIGHT
            count = s16(self.pop())
            dst = self.pop() + s16(self.pop())
            src = self.pop() + s16(self.pop())
            if count > 0:
                self.mem[dst:dst + count] = self.mem[src:src + count]
        elif n == 4:                          # EXIT(seg, proc)
            proc, seg = self.pop(), self.pop()
            self.exit_proc(seg, proc)
        elif n in (5, 6):                     # UNITREAD / UNITWRITE
            mode, block, count = self.pop(), self.pop(), s16(self.pop())
            addr = (self.pop() + s16(self.pop())) & 0xFFFF
            unit = self.pop()
            self._unit_io(n == 6, unit, addr, count, block)
        elif n == 10:                         # FILLCHAR(addr, offset, count, ch)
            ch, count = self.pop() & 0xFF, s16(self.pop())
            addr = self.pop() + s16(self.pop())
            if count > 0:
                self.mem[addr:addr + count] = bytes([ch]) * count
        elif n == 1:                          # NEW(var ptr, words)
            words, ptr = self.pop(), self.pop()
            self.store(ptr, self.heap_top)
            self.heap_top += 2 * words
            self.heap_high = max(self.heap_high, self.heap_top)
            self._check_stack()
        elif n == 32:                         # MARK(var ptr)
            self.store(self.pop(), self.heap_top)
        elif n == 33:                         # RELEASE(var ptr)
            self.heap_top = self.load(self.pop())
            self.heap_high = max(self.heap_high, self.heap_top)
        elif n == 34:                         # IORESULT
            self.push(self.io_result)
        elif n == 38:                         # UNITCLEAR(unit)
            unit = self.pop()
            self.io_result = 0
            if unit == 1 and self.key_seen:   # clears the key the title loop saw
                self.key_seen = False
                self._take_key()
        elif n in (21, 22):                   # GETSEG / RELSEG: segments load on call anyway
            self.pop()
        elif n == 39:                         # HALT
            raise Halted()
        elif n == 40:                         # MEMAVAIL (words)
            self.push((self.sp - 2 * len(self.stack) - self.heap_top) // 2)
        elif n == 0:                          # IOCHECK
            if self.io_result:
                raise VMError(10, f'IORESULT {self.io_result}')
        else:
            raise VMError(11, f'CSP {pcode.CSP_NAMES.get(n, n)}')

    def _unit_io(self, write, unit, addr, count, block):
        if unit in (1, 2):                    # CONSOLE (echoes) and SYSTERM (does not)
            self.io_result = 0
            for k in range(count):
                if write:
                    self.console.put(self.mem[addr + k])
                else:
                    key = self._take_key()
                    self.mem[addr + k] = key
                    if unit == 1:
                        self.console.put(key)
            return
        device = self.drive1 if unit == 4 else self.units.get(unit)
        if write and unit == 4 and self.drive1_readonly:
            self.io_result = 16               # write-protected
            return
        if device is None:
            self.io_result = 9                # no such volume
            return
        self.io_result = 0
        if write:
            device.write(block, self.mem[addr:addr + count])
        else:
            self.mem[addr:addr + count] = device.read(block, count)

    # -- Pascal OS entry points (CXP 0,n) -----------------------------------------------
    def call_os(self, n):
        c = self.console
        if n == 17:                           # WRITE(f, ch:width)
            width, ch, _ = s16(self.pop()), self.pop(), self.pop()
            c.write(' ' * max(0, width - 1))
            c.put(ch & 0xFF)
        elif n == 19:                         # WRITE(f, s:width)
            width, addr, _ = s16(self.pop()), self.pop(), self.pop()
            text = self.pstring(addr)
            c.write(' ' * max(0, width - len(text)) + text)
        elif n == 13:                         # WRITE(f, i:width)
            width, value, _ = s16(self.pop()), s16(self.pop()), self.pop()
            c.write(str(value).rjust(width))
        elif n == 22:                         # WRITELN(f)
            self.pop()
            c.put(13)
        elif n == 29:                         # GOTOXY(x, y)
            y, x = s16(self.pop()), s16(self.pop())
            c.goto(x, y)
        elif n == 16:                         # READ(f, var ch)
            addr, _ = self.pop(), self.pop()
            key = self._take_key()
            self.eoln = key == 13
            if self.eoln:
                key = 32
            elif 32 <= key < 127:
                c.put(key)                    # INPUT echoes
            self.store(addr, key)
        elif n == 21:                         # READLN(f)
            self.pop()
            if self.eoln:
                self.eoln = False
            else:
                while self._take_key() != 13:
                    pass
        elif n == 11:                         # EOLN(f), a function
            self.pop(), self.pop(), self.pop()
            self.push(int(self.eoln))
        elif n == 23:                         # CONCAT step: dest := dest + src
            _, src, dst = self.pop(), self.pop(), self.pop()
            combined = (self.pstring(dst) + self.pstring(src))[:255]
            self.mem[dst] = len(combined)
            self.mem[dst + 1:dst + 1 + len(combined)] = combined.encode('latin1')
        elif n == 25:                         # COPY(src, dst, index, count)
            count, index, dst, src = s16(self.pop()), s16(self.pop()), self.pop(), self.pop()
            text = self.pstring(src)[max(0, index - 1):max(0, index - 1) + max(0, count)]
            self.mem[dst] = len(text)
            self.mem[dst + 1:dst + 1 + len(text)] = text.encode('latin1')
        elif n == 3:                          # FINIT(f, window, record size)
            self.pop(), self.pop(), self.pop()
        elif n == 5:                          # FOPEN(f, name, isold, junk)
            _, _, name, fib = self.pop(), self.pop(), self.pop(), self.pop()
            try:
                self.files[fib] = self.drive1.disk.entry(self.pstring(name))
                self.io_result = 0
            except KeyError:
                self.io_result = 10           # no such file
        elif n == 6:                          # FCLOSE(f, mode)
            self.pop()
            self.files.pop(self.pop(), None)
        elif n == 28:                         # FBLOCKIO(f, buf, offset, nblocks, rblock, doread)
            self.pop(), self.pop()            # function result words
            doread, rblock, nblocks = self.pop(), s16(self.pop()), s16(self.pop())
            offset, buf, fib = s16(self.pop()), self.pop(), self.pop()
            entry = self.files.get(fib)
            if entry is None or not doread & 1:
                raise VMError(11, 'FBLOCKIO: only reads of open files are supported')
            count = max(0, min(nblocks, entry.next_block - entry.first_block - rblock))
            addr = (buf + offset) & 0xFFFF
            self.mem[addr:addr + 512 * count] = self.drive1.read(entry.first_block + rblock, 512 * count)
            self.io_result = 0
            self.push(count)
        else:
            raise VMError(11, f'OS procedure {n}')

    def _take_key(self):
        self.polls_left = None
        return self.console.read_key()
