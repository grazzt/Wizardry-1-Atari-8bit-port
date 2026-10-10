"""Apple Pascal 1.1 (UCSD II.1) p-code decoder.

Operand encodings:
    UB  unsigned byte          SB  signed byte (jump displacement)
    DB  lexical-level byte     B   "big": one byte < 128, else two bytes,
                                   ((b0 & 0x7F) << 8) | b1
    W   little-endian word
Jumps with a negative displacement go through the procedure's jump table:
the entry at JTAB + displacement is a self-relative pointer to the target.
"""
from dataclasses import dataclass
from .codefile import Procedure, self_relative, word

# Opcode -> (mnemonic, operand pattern). Patterns are decoded by `decode`.
OPCODES = {
    128: ('ABI', ''), 129: ('ABR', ''), 130: ('ADI', ''), 131: ('ADR', ''),
    132: ('LAND', ''), 133: ('DIF', ''), 134: ('DVI', ''), 135: ('DVR', ''),
    136: ('CHK', ''), 137: ('FLO', ''), 138: ('FLT', ''), 139: ('INN', ''),
    140: ('INT', ''), 141: ('LOR', ''), 142: ('MODI', ''), 143: ('MPI', ''),
    144: ('MPR', ''), 145: ('NGI', ''), 146: ('NGR', ''), 147: ('LNOT', ''),
    148: ('SRS', ''), 149: ('SBI', ''), 150: ('SBR', ''), 151: ('SGS', ''),
    152: ('SQI', ''), 153: ('SQR', ''), 154: ('STO', ''), 155: ('IXS', ''),
    156: ('UNI', ''), 157: ('LDE', 'UB B'), 158: ('CSP', 'CSP'), 159: ('LDCN', ''),
    160: ('ADJ', 'UB'), 161: ('FJP', 'JMP'), 162: ('INC', 'B'), 163: ('IND', 'B'),
    164: ('IXA', 'B'), 165: ('LAO', 'B'), 166: ('LSA', 'STR'), 167: ('LAE', 'UB B'),
    168: ('MOV', 'B'), 169: ('LDO', 'B'), 170: ('SAS', 'UB'), 171: ('SRO', 'B'),
    172: ('XJP', 'XJP'), 173: ('RNP', 'UB'), 174: ('CIP', 'UB'), 175: ('EQU', 'CMP'),
    176: ('GEQ', 'CMP'), 177: ('GRT', 'CMP'), 178: ('LDA', 'UB B'), 179: ('LDC', 'LDC'),
    180: ('LEQ', 'CMP'), 181: ('LES', 'CMP'), 182: ('LOD', 'UB B'), 183: ('NEQ', 'CMP'),
    184: ('STR', 'UB B'), 185: ('UJP', 'JMP'), 186: ('LDP', ''), 187: ('STP', ''),
    188: ('LDM', 'UB'), 189: ('STM', 'UB'), 190: ('LDB', ''), 191: ('STB', ''),
    192: ('IXP', 'UB UB'), 193: ('RBP', 'UB'), 194: ('CBP', 'UB'), 195: ('EQUI', ''),
    196: ('GEQI', ''), 197: ('GRTI', ''), 198: ('LLA', 'B'), 199: ('LDCI', 'W'),
    200: ('LEQI', ''), 201: ('LESI', ''), 202: ('LDL', 'B'), 203: ('NEQI', ''),
    204: ('STL', 'B'), 205: ('CXP', 'UB UB'), 206: ('CLP', 'UB'), 207: ('CGP', 'UB'),
    208: ('LPA', 'STR'), 209: ('STE', 'UB B'), 211: ('EFJ', 'JMP'), 212: ('NFJ', 'JMP'),
    213: ('BPT', 'B'), 214: ('XIT', ''), 215: ('NOP', ''),
}
for i in range(16):
    OPCODES[216 + i] = (f'SLDL{i + 1}', '')
    OPCODES[232 + i] = (f'SLDO{i + 1}', '')
for i in range(8):
    OPCODES[248 + i] = (f'SIND{i}', '')

# Standard procedures called through CSP.
CSP_NAMES = {
    0: 'IOCHECK', 1: 'NEW', 2: 'MOVELEFT', 3: 'MOVERIGHT', 4: 'EXIT', 5: 'UNITREAD',
    6: 'UNITWRITE', 7: 'IDSEARCH', 8: 'TREESEARCH', 9: 'TIME', 10: 'FILLCHAR',
    11: 'SCAN', 12: 'UNITSTATUS', 21: 'GETSEG', 22: 'RELSEG', 23: 'TRUNC', 24: 'ROUND',
    25: 'SIN', 26: 'COS', 27: 'LOG', 28: 'ATAN', 29: 'LN', 30: 'EXP', 31: 'SQRT',
    32: 'MARK', 33: 'RELEASE', 34: 'IORESULT', 35: 'UNITBUSY', 36: 'PWROFTEN',
    37: 'UNITWAIT', 38: 'UNITCLEAR', 39: 'HALT', 40: 'MEMAVAIL',
}

# Procedures in segment 0 (PASCALSY, in SYSTEM.PASCAL) reached by CXP 0,n.
# Each was confirmed against the statement that generated it in Ewers's
# WIZARDRY.CODE listing; unused entry points are omitted.
PASCALSY_PROCS = {
    11: 'EOLN', 13: 'WRITE(integer)', 16: 'READ(char)', 17: 'WRITE(char)',
    19: 'WRITE(string)', 21: 'READLN', 22: 'WRITELN', 23: 'CONCAT', 25: 'COPY',
    29: 'GOTOXY',
}

# Intrinsic units in the SYSTEM.LIBRARY on the Wizardry boot disk, by segment number.
LIBRARY_UNITS = {20: 'TURTLEGRAPHICS', 22: 'APPLESTUFF', 28: 'CHAINSTUFF',
                 29: 'TRANSCEND', 30: 'LONGINTIO', 31: 'PASCALIO'}

# Comparison type byte.
CMP_TYPES = {2: 'REAL', 4: 'STR', 6: 'BOOL', 8: 'SET', 10: 'BYTES', 12: 'WORDS'}

RETURNS = {'RNP', 'RBP', 'XIT'}


@dataclass
class Instruction:
    offset: int          # within the segment
    length: int
    mnemonic: str
    operands: list       # decoded operand values
    text: str            # operand text for display
    targets: tuple = ()  # jump destinations within the segment

    @property
    def end(self):
        return self.offset + self.length


class DecodeError(ValueError):
    pass


def _signed(value):
    return value - 0x10000 if value & 0x8000 else value


def _big(code, i):
    b0 = code[i]
    if b0 & 0x80:
        return ((b0 & 0x7F) << 8) | code[i + 1], 2
    return b0, 1


def _jump(code, at, disp, jtab):
    if disp >= 0:
        return at + disp
    entry = jtab + disp
    return self_relative(code, entry)


def decode(code: bytes, offset: int, jtab: int) -> Instruction:
    op = code[offset]
    if op < 128:
        return Instruction(offset, 1, 'SLDC', [op], str(op))
    if op not in OPCODES:
        raise DecodeError(f'unknown opcode {op} at {offset:#06x}')
    name, pattern = OPCODES[op]
    i = offset + 1
    operands, text, targets = [], '', ()
    if pattern in ('UB', 'UB UB'):
        operands = list(code[i:i + len(pattern.split())])
        i += len(operands)
        text = ', '.join(map(str, operands))
        if name == 'CXP' and operands[0] == 0 and operands[1] in PASCALSY_PROCS:
            text += f'  ; {PASCALSY_PROCS[operands[1]]}'
    elif pattern == 'B':
        value, n = _big(code, i)
        i += n
        operands, text = [value], str(value)
    elif pattern == 'UB B':
        level = code[i]
        value, n = _big(code, i + 1)
        i += 1 + n
        operands, text = [level, value], f'{level}, {value}'
    elif pattern == 'W':
        value = word(code, i)
        i += 2
        operands, text = [value], str(value - 0x10000 if value & 0x8000 else value)
    elif pattern == 'JMP':
        disp = code[i] - 256 if code[i] & 0x80 else code[i]
        i += 1
        target = _jump(code, i, disp, jtab)
        operands, text, targets = [disp], f'{target:#06x}', (target,)
    elif pattern == 'CSP':
        n = code[i]
        i += 1
        operands, text = [n], CSP_NAMES.get(n, f'csp{n}')
    elif pattern == 'CMP':
        kind = code[i]
        i += 1
        operands, text = [kind], CMP_TYPES.get(kind, str(kind))
        if kind in (10, 12):
            size, n = _big(code, i)
            i += n
            operands.append(size)
            text += f', {size}'
    elif pattern == 'STR':
        n = code[i]
        raw = code[i + 1:i + 1 + n]
        i += 1 + n
        operands = [raw]
        text = repr(raw.decode('latin1')) if name == 'LSA' else raw.hex(' ')
    elif pattern == 'LDC':
        count = code[i]
        i += 1
        i += i & 1                                    # word aligned
        values = [word(code, i + 2 * k) for k in range(count)]
        i += 2 * count
        operands, text = values, ' '.join(f'{v:04x}' for v in values)
    elif pattern == 'XJP':
        i += i & 1                                    # word aligned
        low, high = _signed(word(code, i)), _signed(word(code, i + 2))
        if code[i + 4] != 185:
            raise DecodeError(f'XJP at {offset:#06x}: expected UJP for the default case')
        disp = code[i + 5] - 256 if code[i + 5] & 0x80 else code[i + 5]
        default = _jump(code, i + 6, disp, jtab)
        i += 6
        cases = []
        for _ in range(high - low + 1):
            cases.append(self_relative(code, i))
            i += 2
        operands = [low, high, default, cases]
        text = f'{low}..{high} else {default:#06x}'
        targets = (default, *cases)
    return Instruction(offset, i - offset, name, operands, text, targets)


def disassemble(code: bytes, proc: Procedure):
    """Decode a p-code procedure from ENTERIC through its returning exit code.

    Returns the instruction list; raises DecodeError if decoding does not end
    exactly on a return at or after EXITIC.
    """
    if proc.native:
        raise ValueError('native procedure; use m6502.disassemble')
    out = []
    pc = proc.enter
    limit = proc.jtab - 8
    while pc < limit:
        ins = decode(code, pc, proc.jtab)
        out.append(ins)
        pc = ins.end
        if ins.mnemonic in RETURNS and ins.offset >= proc.exit:
            return out
    raise DecodeError(f'procedure {proc.number}: ran into the attribute table at {pc:#06x}')
