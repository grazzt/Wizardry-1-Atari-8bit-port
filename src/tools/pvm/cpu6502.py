"""A small NMOS 6502 core for running Wizardry's native routines.

Only documented opcodes are implemented, in binary mode; decimal mode raises,
because none of the native routines use it. Memory is shared with the
p-machine. `io_read`/`io_write` see every access to $C000-$C0FF (Apple soft
switches), and `traps` maps addresses to host callbacks that run instead of a
JSR, so BIOS entry points can be supplied by the host.
"""
from ucsd.m6502 import OPCODES

_SIZES = {'imp': 0, 'acc': 0, 'imm': 1, 'zp': 1, 'zpx': 1, 'zpy': 1, 'izx': 1, 'izy': 1,
          'abs': 2, 'abx': 2, 'aby': 2, 'ind': 2, 'rel': 1}


class CPUError(RuntimeError):
    pass


class CPU6502:
    def __init__(self, memory, io_read=None, io_write=None):
        self.m = memory
        self.a = self.x = self.y = 0
        self.s = 0xFF
        self.pc = 0
        self.n = self.v = self.d = self.i = self.z = self.c = 0
        self.io_read = io_read or (lambda addr: 0)
        self.io_write = io_write or (lambda addr, value: None)
        self.traps = {}
        self.cycles = 0

    # -- memory -------------------------------------------------------------
    def read(self, addr):
        if 0xC000 <= addr <= 0xC0FF:
            return self.io_read(addr) & 0xFF
        return self.m[addr]

    def write(self, addr, value):
        if 0xC000 <= addr <= 0xC0FF:
            self.io_write(addr, value)
        else:
            self.m[addr] = value & 0xFF

    def push(self, value):
        self.m[0x100 + self.s] = value & 0xFF
        self.s = (self.s - 1) & 0xFF

    def pull(self):
        self.s = (self.s + 1) & 0xFF
        return self.m[0x100 + self.s]

    # -- flags --------------------------------------------------------------
    def _nz(self, value):
        self.n = value >> 7 & 1
        self.z = int(value == 0)
        return value

    def get_p(self):
        return (self.n << 7 | self.v << 6 | 0x20 | self.d << 3 | self.i << 2 | self.z << 1 | self.c)

    def set_p(self, p):
        self.n, self.v, self.d = p >> 7 & 1, p >> 6 & 1, p >> 3 & 1
        self.i, self.z, self.c = p >> 2 & 1, p >> 1 & 1, p & 1

    # -- execution ----------------------------------------------------------
    def _address(self, mode):
        m, pc = self.m, self.pc
        if mode == 'imm':
            return pc + 1
        if mode == 'zp':
            return m[pc + 1]
        if mode == 'zpx':
            return (m[pc + 1] + self.x) & 0xFF
        if mode == 'zpy':
            return (m[pc + 1] + self.y) & 0xFF
        if mode == 'abs':
            return m[pc + 1] | m[pc + 2] << 8
        if mode == 'abx':
            return ((m[pc + 1] | m[pc + 2] << 8) + self.x) & 0xFFFF
        if mode == 'aby':
            return ((m[pc + 1] | m[pc + 2] << 8) + self.y) & 0xFFFF
        if mode == 'izx':
            zp = (m[pc + 1] + self.x) & 0xFF
            return m[zp] | m[(zp + 1) & 0xFF] << 8
        if mode == 'izy':
            zp = m[pc + 1]
            return ((m[zp] | m[(zp + 1) & 0xFF] << 8) + self.y) & 0xFFFF
        if mode == 'ind':   # NMOS page-wrap bug preserved
            ptr = m[pc + 1] | m[pc + 2] << 8
            hi = (ptr & 0xFF00) | ((ptr + 1) & 0xFF)
            return m[ptr] | m[hi] << 8
        raise CPUError(mode)

    def _adc(self, value):
        if self.d:
            raise CPUError(f'decimal-mode ADC/SBC at ${self.pc:04X}')
        total = self.a + value + self.c
        self.v = int(~(self.a ^ value) & (self.a ^ total) & 0x80 != 0)
        self.c = int(total > 0xFF)
        self.a = self._nz(total & 0xFF)

    def _compare(self, reg, value):
        self.c = int(reg >= value)
        self._nz((reg - value) & 0xFF)

    def run(self, pc, stop, limit=10_000_000):
        """Execute from `pc` until the PC reaches `stop`."""
        self.pc = pc
        steps = 0
        while self.pc != stop:
            if self.pc in self.traps:
                self.traps[self.pc](self)
                self.pc = (self.pull() | self.pull() << 8) + 1     # behave like RTS
                continue
            steps += 1
            if steps > limit:
                raise CPUError(f'native code ran more than {limit} instructions (PC ${self.pc:04X})')
            self.step()
        self.cycles += steps

    def step(self):
        op = self.m[self.pc]
        if op not in OPCODES:
            raise CPUError(f'illegal opcode ${op:02X} at ${self.pc:04X}')
        name, mode = OPCODES[op]
        size = 1 + _SIZES[mode]
        nxt = (self.pc + size) & 0xFFFF
        if mode in ('imp', 'acc', 'rel'):
            addr = None
        else:
            addr = self._address(mode)

        if name == 'LDA':
            self.a = self._nz(self.read(addr))
        elif name == 'LDX':
            self.x = self._nz(self.read(addr))
        elif name == 'LDY':
            self.y = self._nz(self.read(addr))
        elif name == 'STA':
            self.write(addr, self.a)
        elif name == 'STX':
            self.write(addr, self.x)
        elif name == 'STY':
            self.write(addr, self.y)
        elif name in ('ADC', 'SBC'):
            value = self.read(addr)
            self._adc(value if name == 'ADC' else value ^ 0xFF)
        elif name == 'AND':
            self.a = self._nz(self.a & self.read(addr))
        elif name == 'ORA':
            self.a = self._nz(self.a | self.read(addr))
        elif name == 'EOR':
            self.a = self._nz(self.a ^ self.read(addr))
        elif name == 'CMP':
            self._compare(self.a, self.read(addr))
        elif name == 'CPX':
            self._compare(self.x, self.read(addr))
        elif name == 'CPY':
            self._compare(self.y, self.read(addr))
        elif name == 'BIT':
            value = self.read(addr)
            self.n, self.v, self.z = value >> 7 & 1, value >> 6 & 1, int(self.a & value == 0)
        elif name in ('ASL', 'LSR', 'ROL', 'ROR'):
            value = self.a if mode == 'acc' else self.read(addr)
            if name == 'ASL':
                self.c, value = value >> 7, (value << 1) & 0xFF
            elif name == 'LSR':
                self.c, value = value & 1, value >> 1
            elif name == 'ROL':
                self.c, value = value >> 7, ((value << 1) | self.c) & 0xFF
            else:
                self.c, value = value & 1, (value >> 1) | (self.c << 7)
            self._nz(value)
            if mode == 'acc':
                self.a = value
            else:
                self.write(addr, value)
        elif name in ('INC', 'DEC'):
            value = self._nz((self.read(addr) + (1 if name == 'INC' else -1)) & 0xFF)
            self.write(addr, value)
        elif name == 'INX':
            self.x = self._nz((self.x + 1) & 0xFF)
        elif name == 'INY':
            self.y = self._nz((self.y + 1) & 0xFF)
        elif name == 'DEX':
            self.x = self._nz((self.x - 1) & 0xFF)
        elif name == 'DEY':
            self.y = self._nz((self.y - 1) & 0xFF)
        elif name == 'TAX':
            self.x = self._nz(self.a)
        elif name == 'TAY':
            self.y = self._nz(self.a)
        elif name == 'TXA':
            self.a = self._nz(self.x)
        elif name == 'TYA':
            self.a = self._nz(self.y)
        elif name == 'TSX':
            self.x = self._nz(self.s)
        elif name == 'TXS':
            self.s = self.x
        elif name == 'PHA':
            self.push(self.a)
        elif name == 'PLA':
            self.a = self._nz(self.pull())
        elif name == 'PHP':
            self.push(self.get_p() | 0x10)
        elif name == 'PLP':
            self.set_p(self.pull())
        elif mode == 'rel':
            taken = {'BPL': not self.n, 'BMI': self.n, 'BVC': not self.v, 'BVS': self.v,
                     'BCC': not self.c, 'BCS': self.c, 'BNE': not self.z, 'BEQ': self.z}[name]
            if taken:
                offset = self.m[self.pc + 1]
                nxt = (nxt + (offset - 256 if offset & 0x80 else offset)) & 0xFFFF
        elif name == 'JMP':
            nxt = addr
        elif name == 'JSR':
            ret = (self.pc + 2) & 0xFFFF
            self.push(ret >> 8)
            self.push(ret)
            nxt = addr
        elif name == 'RTS':
            nxt = ((self.pull() | self.pull() << 8) + 1) & 0xFFFF
        elif name == 'RTI':
            self.set_p(self.pull())
            nxt = self.pull() | self.pull() << 8
        elif name in ('CLC', 'SEC'):
            self.c = int(name == 'SEC')
        elif name in ('CLD', 'SED'):
            self.d = int(name == 'SED')
        elif name in ('CLI', 'SEI'):
            self.i = int(name == 'SEI')
        elif name == 'CLV':
            self.v = 0
        elif name == 'NOP':
            pass
        elif name == 'BRK':
            raise CPUError(f'BRK at ${self.pc:04X}')
        else:
            raise CPUError(f'unimplemented {name}')
        self.pc = nxt
