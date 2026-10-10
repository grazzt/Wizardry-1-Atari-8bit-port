"""Read Wizardry I SCENARIO.DATA from an Apple scenario disk image.

    python3 tools/wizardry_scenario.py toc IMAGE
    python3 tools/wizardry_scenario.py roster IMAGE
    python3 tools/wizardry_scenario.py diff IMAGE_A IMAGE_B

Layouts come from Ewers's reconstructed Pascal (TSCNTOC, TCHAR). Record sizes
are the SIZEOF constants the game passes to GETREC; they were read from the
p-code calls, not assumed.
"""
import argparse
from collections import Counter
import struct
import sys

from ucsd.disk import PascalDisk

TYPES = ['ZZERO', 'ZMAZE', 'ZENEMY', 'ZREWARD', 'ZOBJECT', 'ZCHAR', 'ZSPCCHRS', 'ZEXP']
RECORD_SIZE = {'ZZERO': 504, 'ZMAZE': 894, 'ZENEMY': 158, 'ZREWARD': 168,
               'ZOBJECT': 78, 'ZCHAR': 208, 'ZSPCCHRS': 512, 'ZEXP': 624}
CACHE = 1024   # GETREC reads two blocks at a time


def pstring(data, offset, capacity):
    """A Pascal STRING[capacity]: length byte then characters."""
    return data[offset + 1:offset + 1 + min(data[offset], capacity)].decode('latin1')


def pstrings(data, offset, count, capacity):
    stride = (capacity + 2) & ~1          # unpacked strings are word aligned
    return [pstring(data, offset + i * stride, capacity) for i in range(count)], offset + count * stride


class Scenario:
    def __init__(self, image):
        disk = image if isinstance(image, PascalDisk) else PascalDisk.open(image)
        self.data = disk.read('SCENARIO.DATA')
        d = self.data
        self.name = pstring(d, 0, 40)
        self.per_cache = dict(zip(TYPES, struct.unpack_from('<8h', d, 42)))
        self.on_disk = dict(zip(TYPES, struct.unpack_from('<8h', d, 58)))
        self.first_block = dict(zip(TYPES, struct.unpack_from('<8h', d, 90)))
        offset = 106
        self.races, offset = pstrings(d, offset, 6, 9)
        self.classes, offset = pstrings(d, offset, 8, 9)
        self.statuses, offset = pstrings(d, offset, 8, 8)
        self.alignments, offset = pstrings(d, offset, 4, 9)

    def record_offset(self, kind, index):
        per = self.per_cache[kind]
        return (self.first_block[kind] + 2 * (index // per)) * 512 + (index % per) * RECORD_SIZE[kind]

    def record(self, kind, index):
        offset = self.record_offset(kind, index)
        return self.data[offset:offset + RECORD_SIZE[kind]]

    def locate(self, offset):
        """Map a byte offset to (type, record index), or (type, None) for slack bytes."""
        block = offset // 512
        kind = max((k for k in TYPES if self.first_block[k] <= block), key=lambda k: self.first_block[k])
        chunk, within = divmod(offset - self.first_block[kind] * 512, CACHE)
        index, rest = divmod(within, RECORD_SIZE[kind])
        if index >= self.per_cache[kind] or chunk * self.per_cache[kind] + index >= self.on_disk[kind]:
            return kind, None
        return kind, chunk * self.per_cache[kind] + index

    def roster(self):
        for i in range(self.on_disk['ZCHAR']):
            r = self.record('ZCHAR', i)
            in_maze, race, cls, age, status, align = struct.unpack_from('<6h', r, 32)
            yield i, pstring(r, 0, 15), bool(in_maze), race, cls, age, status, align


def enum(names, value):
    return names[value] if 0 <= value < len(names) else f'?{value}'


def cmd_toc(args):
    s = Scenario(args.image)
    print(f'{s.name!r}')
    print(f'{"type":9} {"records":>7} {"per 1K":>6} {"block":>5} {"size":>5}')
    for k in TYPES:
        print(f'{k:9} {s.on_disk[k]:7} {s.per_cache[k]:6} {s.first_block[k]:5} {RECORD_SIZE[k]:5}')
    print('races:     ', ', '.join(s.races))
    print('classes:   ', ', '.join(s.classes))
    print('statuses:  ', ', '.join(s.statuses))
    print('alignments:', ', '.join(s.alignments))


def cmd_roster(args):
    s = Scenario(args.image)
    for i, name, in_maze, race, cls, age, status, align in s.roster():
        print(f'{i:2} {name:15} {enum(s.races, race):7} {enum(s.classes, cls):8} '
              f'{enum(s.alignments, align):8} {enum(s.statuses, status):7} '
              f'age {age // 52:3}{"  (in maze)" if in_maze else ""}')


def cmd_diff(args):
    a, b = Scenario(args.image_a), Scenario(args.image_b)
    counts = Counter(a.locate(i) for i in range(len(a.data)) if a.data[i] != b.data[i])
    if not counts:
        print('SCENARIO.DATA is identical')
        return
    print(f'{sum(counts.values())} bytes differ:')
    for (kind, index), n in sorted(counts.items(), key=lambda kv: (TYPES.index(kv[0][0]), kv[0][1] or -1)):
        print(f'  {kind:9} {"slack" if index is None else f"record {index}":>10}  {n:4} bytes')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = parser.add_subparsers(dest='command', required=True)
    for name, fn in [('toc', cmd_toc), ('roster', cmd_roster)]:
        p = sub.add_parser(name)
        p.add_argument('image')
        p.set_defaults(fn=fn)
    p = sub.add_parser('diff')
    p.add_argument('image_a')
    p.add_argument('image_b')
    p.set_defaults(fn=cmd_diff)
    args = parser.parse_args(argv)
    args.fn(args)


if __name__ == '__main__':
    sys.exit(main())
