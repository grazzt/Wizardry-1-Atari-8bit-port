"""Apple Pascal 1.1 (UCSD II.1) code files: segments and procedures.

Block 0 of a code file is the segment dictionary. Each segment ends with a
procedure dictionary: the final word holds the segment number (low byte) and
procedure count (high byte); the words before it are self-relative pointers to
each procedure's attribute table, procedure 1 nearest the end.

A p-code procedure's attribute table, relative to its JTAB address:

    JTAB+1  lex level         JTAB+0  procedure number (0 = native 6502 code)
    JTAB-2  ENTERIC  (self-relative)   JTAB-4  EXITIC (self-relative)
    JTAB-6  parameter bytes            JTAB-8  local data bytes
    JTAB-10 ... jump-table entries (self-relative), reached by negative jump offsets
"""
from dataclasses import dataclass, field
import struct

SEGMENT_KINDS = ['linked', 'hostseg', 'segproc', 'unitseg', 'seprtseg',
                 'unlinked_intrins', 'linked_intrins', 'dataseg']


def word(data, offset):
    return struct.unpack_from('<H', data, offset)[0]


def self_relative(data, offset):
    """Resolve a self-relative pointer stored at `offset`."""
    return offset - word(data, offset)


@dataclass
class Procedure:
    number: int
    jtab: int                 # offset of the attribute table within the segment
    native: bool
    lex_level: int = 0
    enter: int = 0            # absolute offsets within the segment
    exit: int = 0
    param_bytes: int = 0
    data_bytes: int = 0


@dataclass
class Segment:
    index: int                # slot in the segment dictionary
    name: str
    kind: str
    block: int                # first block within the code file
    length: int
    number: int = 0           # segment number used by CXP
    mtype: int = 0
    version: int = 0
    code: bytes = b''
    procedures: list = field(default_factory=list)

    def procedure(self, number) -> Procedure:
        for p in self.procedures:
            if p.number == number:
                return p
        raise KeyError(f'{self.name}: no procedure {number}')


class CodeFile:
    def __init__(self, data: bytes):
        self.data = data
        self.segments = []
        d = data[:512]
        for i in range(16):
            block, length = struct.unpack_from('<HH', d, i * 4)
            if not length:
                continue
            name = d[64 + i * 8:72 + i * 8].decode('ascii').rstrip()
            kind = word(d, 192 + i * 2)
            info = word(d, 256 + i * 2)
            seg = Segment(i, name, SEGMENT_KINDS[kind] if kind < 8 else str(kind), block, length,
                          number=info & 0xFF, mtype=(info >> 8) & 15, version=info >> 13)
            seg.code = data[block * 512:block * 512 + length]
            self._read_procedures(seg)
            self.segments.append(seg)
        self.comment = d[432:512].split(b'\0')[0].decode('latin1')

    def segment(self, key) -> Segment:
        for s in self.segments:
            if s.name == str(key).upper() or s.number == key:
                return s
        raise KeyError(f'no segment {key}')

    @staticmethod
    def _read_procedures(seg):
        code = seg.code
        tail = len(code) - 2
        dict_segnum, count = code[tail], code[tail + 1]
        if seg.number == 0:
            seg.number = dict_segnum
        for n in range(1, count + 1):
            ptr = tail - 2 * n
            if word(code, ptr) == 0:
                continue      # procedure slot unused
            jtab = self_relative(code, ptr)
            number, lex = code[jtab], code[jtab + 1]
            if number == 0:
                proc = Procedure(n, jtab, native=True, enter=self_relative(code, jtab - 2))
            else:
                proc = Procedure(n, jtab, native=False, lex_level=lex,
                                 enter=self_relative(code, jtab - 2),
                                 exit=self_relative(code, jtab - 4),
                                 param_bytes=word(code, jtab - 6),
                                 data_bytes=word(code, jtab - 8))
            seg.procedures.append(proc)
