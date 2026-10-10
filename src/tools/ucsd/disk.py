"""Apple II 140K disk images holding an Apple Pascal (UCSD) volume.

Pascal addresses the disk in 512-byte blocks, each made from two 256-byte
sectors. A .dsk/.do image is stored in DOS 3.3 sector order and a .po image in
ProDOS order; the volume directory (block 2) is checked under both orders to
detect which one an image uses.
"""
from dataclasses import dataclass
from datetime import date
import struct

BLOCK = 512
SECTOR = 256

# Pascal/ProDOS block-within-track -> the two DOS 3.3 logical sectors holding it.
_DOS_ORDER = [(0, 14), (13, 12), (11, 10), (9, 8), (7, 6), (5, 4), (3, 2), (1, 15)]

FILE_KINDS = {0: 'none', 1: 'bad', 2: 'code', 3: 'text', 4: 'info', 5: 'data', 6: 'graf', 7: 'foto'}


@dataclass
class DirEntry:
    name: str
    kind: str
    first_block: int
    next_block: int      # first block after the file
    last_bytes: int     # bytes used in the final block
    modified: date | None

    @property
    def size(self):
        return (self.next_block - self.first_block - 1) * BLOCK + self.last_bytes


class PascalDisk:
    def __init__(self, image: bytes, name: str = ''):
        if len(image) != 35 * 16 * SECTOR:
            raise ValueError(f'{name}: expected a 143360-byte 140K image, got {len(image)}')
        self.image = image
        self.name = name
        for order in ('dos', 'prodos'):
            self.order = order
            if self._directory_valid():
                break
        else:
            raise ValueError(f'{name}: no Apple Pascal volume directory found')
        self.volume, self.entries = self._read_directory()

    @classmethod
    def open(cls, path):
        with open(path, 'rb') as f:
            return cls(f.read(), str(path))

    def block(self, n: int) -> bytes:
        if self.order == 'prodos':
            return self.image[n * BLOCK:(n + 1) * BLOCK]
        track, index = divmod(n, 8)
        a, b = _DOS_ORDER[index]
        base = track * 16
        return (self.image[(base + a) * SECTOR:(base + a + 1) * SECTOR] +
                self.image[(base + b) * SECTOR:(base + b + 1) * SECTOR])

    def blocks(self, first: int, count: int) -> bytes:
        return b''.join(self.block(n) for n in range(first, first + count))

    def _directory_valid(self):
        d = self.block(2)
        first, nxt, kind, name_len = struct.unpack_from('<HHHB', d)
        total_blocks = struct.unpack_from('<H', d, 14)[0]
        return first == 0 and nxt == 6 and kind == 0 and 1 <= name_len <= 7 and total_blocks == 280

    def _read_directory(self):
        d = self.blocks(2, 4)
        volume = d[7:7 + d[6]].decode('ascii')
        count = struct.unpack_from('<H', d, 16)[0]
        entries = []
        for i in range(1, count + 1):
            e = d[i * 26:(i + 1) * 26]
            first, nxt, kind = struct.unpack_from('<HHH', e)
            name = e[7:7 + e[6]].decode('ascii')
            last_bytes, stamp = struct.unpack_from('<HH', e, 22)
            entries.append(DirEntry(name, FILE_KINDS.get(kind & 15, str(kind)), first, nxt,
                                    last_bytes, _pascal_date(stamp)))
        return volume, entries

    def entry(self, name: str) -> DirEntry:
        for e in self.entries:
            if e.name.upper() == name.upper():
                return e
        raise KeyError(f'{self.name}: no file {name}')

    def read(self, name: str) -> bytes:
        e = self.entry(name)
        return self.blocks(e.first_block, e.next_block - e.first_block)[:e.size]


def _pascal_date(stamp):
    """Pascal dates pack month (bits 0-3), day (4-8) and year-1900 (9-15)."""
    month, day, year = stamp & 15, (stamp >> 4) & 31, stamp >> 9
    try:
        return date(1900 + year, month, day)
    except ValueError:
        return None


def decode_text(data: bytes) -> str:
    """Convert a Pascal .TEXT file to plain text.

    The first two blocks are an editor header. Lines end in CR; a DLE (16)
    followed by a byte n encodes n-32 leading spaces; NULs pad each 1K page.
    """
    out = []
    body = data[1024:]
    i = 0
    while i < len(body):
        c = body[i]
        if c == 16 and i + 1 < len(body):
            out.append(' ' * max(0, body[i + 1] - 32))
            i += 2
            continue
        if c == 13:
            out.append('\n')
        elif c:
            out.append(chr(c))
        i += 1
    return ''.join(out)
