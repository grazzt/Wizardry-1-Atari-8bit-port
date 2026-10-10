"""Minimal NMOS 6502 disassembler for native procedures in Pascal code files.

A native (assembly) procedure's attribute table has procedure number 0. Below
JTAB-2 (its self-relative entry pointer) are four relocation lists, read
downward: each is a count word followed by that many self-relative word
pointers. The machine code runs from the entry point up to the lowest list.
"""
from .codefile import Procedure, word

# Addressing modes: operand length and format.
_MODES = {
    'imp': (0, ''), 'acc': (0, 'A'), 'imm': (1, '#${:02X}'), 'zp': (1, '${:02X}'),
    'zpx': (1, '${:02X},X'), 'zpy': (1, '${:02X},Y'), 'izx': (1, '(${:02X},X)'),
    'izy': (1, '(${:02X}),Y'), 'abs': (2, '${:04X}'), 'abx': (2, '${:04X},X'),
    'aby': (2, '${:04X},Y'), 'ind': (2, '(${:04X})'), 'rel': (1, '${:04X}'),
}

_TABLE = '''
00 BRK imp 01 ORA izx 05 ORA zp 06 ASL zp 08 PHP imp 09 ORA imm 0A ASL acc 0D ORA abs 0E ASL abs
10 BPL rel 11 ORA izy 15 ORA zpx 16 ASL zpx 18 CLC imp 19 ORA aby 1D ORA abx 1E ASL abx
20 JSR abs 21 AND izx 24 BIT zp 25 AND zp 26 ROL zp 28 PLP imp 29 AND imm 2A ROL acc 2C BIT abs
2D AND abs 2E ROL abs 30 BMI rel 31 AND izy 35 AND zpx 36 ROL zpx 38 SEC imp 39 AND aby 3D AND abx
3E ROL abx 40 RTI imp 41 EOR izx 45 EOR zp 46 LSR zp 48 PHA imp 49 EOR imm 4A LSR acc 4C JMP abs
4D EOR abs 4E LSR abs 50 BVC rel 51 EOR izy 55 EOR zpx 56 LSR zpx 58 CLI imp 59 EOR aby 5D EOR abx
5E LSR abx 60 RTS imp 61 ADC izx 65 ADC zp 66 ROR zp 68 PLA imp 69 ADC imm 6A ROR acc 6C JMP ind
6D ADC abs 6E ROR abs 70 BVS rel 71 ADC izy 75 ADC zpx 76 ROR zpx 78 SEI imp 79 ADC aby 7D ADC abx
7E ROR abx 81 STA izx 84 STY zp 85 STA zp 86 STX zp 88 DEY imp 8A TXA imp 8C STY abs 8D STA abs
8E STX abs 90 BCC rel 91 STA izy 94 STY zpx 95 STA zpx 96 STX zpy 98 TYA imp 99 STA aby 9A TXS imp
9D STA abx A0 LDY imm A1 LDA izx A2 LDX imm A4 LDY zp A5 LDA zp A6 LDX zp A8 TAY imp A9 LDA imm
AA TAX imp AC LDY abs AD LDA abs AE LDX abs B0 BCS rel B1 LDA izy B4 LDY zpx B5 LDA zpx B6 LDX zpy
B8 CLV imp B9 LDA aby BA TSX imp BC LDY abx BD LDA abx BE LDX aby C0 CPY imm C1 CMP izx C4 CPY zp
C5 CMP zp C6 DEC zp C8 INY imp C9 CMP imm CA DEX imp CC CPY abs CD CMP abs CE DEC abs D0 BNE rel
D1 CMP izy D5 CMP zpx D6 DEC zpx D8 CLD imp D9 CMP aby DD CMP abx DE DEC abx E0 CPX imm E1 SBC izx
E4 CPX zp E5 SBC zp E6 INC zp E8 INX imp E9 SBC imm EA NOP imp EC CPX abs ED SBC abs EE INC abs
F0 BEQ rel F1 SBC izy F5 SBC zpx F6 INC zpx F8 SED imp F9 SBC aby FD SBC abx FE INC abx
'''.split()
OPCODES = {int(_TABLE[i], 16): (_TABLE[i + 1], _TABLE[i + 2]) for i in range(0, len(_TABLE), 3)}


def native_layout(code: bytes, proc: Procedure):
    """Return (code_end, relocation_lists) for a native procedure."""
    pos = proc.jtab - 4
    lists = []
    for _ in range(4):
        count = word(code, pos)
        entries = [pos - 2 * (k + 1) for k in range(count)]
        lists.append([e - word(code, e) for e in entries])
        pos -= 2 * (count + 1)
    return pos + 2, lists


def disassemble(code: bytes, proc: Procedure):
    """Yield (offset, bytes, text) lines for a native procedure.

    Offsets are relative to the procedure entry, as in Ewers's assembler
    listing. Bytes that are not a documented opcode are shown as .BYTE.
    """
    end, _ = native_layout(code, proc)
    pc = proc.enter
    while pc < end:
        op = code[pc]
        if op not in OPCODES or pc + 1 + _MODES[OPCODES[op][1]][0] > end:
            yield pc - proc.enter, code[pc:pc + 1], f'.BYTE ${op:02X}'
            pc += 1
            continue
        name, mode = OPCODES[op]
        size, fmt = _MODES[mode]
        raw = code[pc:pc + 1 + size]
        if size == 1:
            value = raw[1]
            if mode == 'rel':
                value = pc + 2 + (value - 256 if value & 0x80 else value) - proc.enter
        elif size == 2:
            value = raw[1] | raw[2] << 8
        text = name + (' ' + fmt.format(value) if size else (' A' if mode == 'acc' else ''))
        yield pc - proc.enter, raw, text
        pc += 1 + size
