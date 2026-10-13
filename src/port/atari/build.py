"""Build Wizardry for the Atari as one bootable disk image.

    python3 port/atari/build.py [--scenario IMAGE] [--no-title] [--testmode] [--trace]

IMAGE is an Apple .dsk, or an .atr from an earlier build: its scenario volume,
with the characters saved on it, is carried over to the new disk.

Output in port/atari/build/:
  wizardry.atr   bootable, single density: the boot sectors carry the p-machine
                 runtime (loaded at $06FA), then its tables and extra code (for
                 $B000), then two Apple Pascal volumes of 280 blocks (1120
                 sectors) each: the boot disk (SYSTEM.STARTUP and the title
                 picture file WT; read-only, as drive 1 while the title and
                 options run) and the scenario disk (the game's drive 1 after
                 SYSTEM.STARTUP chains to WIZARDRY.CODE). Copy protection is
                 patched out of both programs (tools/pvm/patches.py).
  layout.json    sector layout of the disk (BOOTVOL, SCENVOL etc.)
  labels.txt     ld65 label file, for debugging

The scenario volume already holds everything the game reads: WIZARDRY.CODE,
SCENARIO.DATA and SCENARIO.MESGS, so the game's own FINDFILE works unchanged.
"""
import argparse
import json
from pathlib import Path
import struct
import subprocess
import sys

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
sys.path.insert(0, str(PROJECT / 'tools'))

from ucsd.codefile import CodeFile                      # noqa: E402
from ucsd.disk import DirEntry, PascalDisk              # noqa: E402
from pvm import patches                                  # noqa: E402
import music                                             # noqa: E402
import pictures                                          # noqa: E402
import zx02
import twodisk_music
import compress                                          # noqa: E402
import party

TOOLCHAIN = PROJECT / 'tools/toolchain/local/bin'
LOAD = 0x06FA             # boot header; code proper starts at $0700

BOOT = PROJECT / 'appleII/images/wizardry_i/wizardry_i_boot.dsk'
# The NES version's music (an NSF rip, kept out of Git): played on the title.
NES_MUSIC = PROJECT / 'nes/snafaru/wiz1.nsf'

# --- the compressed scenario volume (the two-disk build's disk 2) -------------------
#
# Preserve the Pascal directory and code header at their original sectors.
# Pack independent code segments and read-only blocks without sector padding;
# relocate writable 1 KB caches as raw, sector-aligned blocks. The map restores
# virtual Pascal block addresses for both reads and writes. PCE picture records
# follow the volume arena, independently compressed without changing pixels.
MAP_MAGIC = b'WZC3'
DIR_BLOCKS = 7
MAP_START_SECTOR = 1 + 4 * DIR_BLOCKS


def writable_data_blocks(disk):
    """Every 1 KB cache the original game can dirty (file-relative blocks).

    GETRECW writes mazes, Boltac inventory and characters. ENMYREWD writes
    an enemy cache only when TENEMY.UNIQUE (offset 148) is positive; it
    only decrements that counter, so other enemy caches remain immutable.
    Keep both blocks of each cache raw, including its unused trailing bytes.
    """
    from wizardry_scenario import Scenario
    scenario = Scenario(disk)
    writable = set()
    for kind in ('ZMAZE', 'ZOBJECT', 'ZCHAR', 'ZENEMY'):
        for index in range(scenario.on_disk[kind]):
            if kind == 'ZENEMY' and struct.unpack_from('<h', scenario.record(kind, index), 148)[0] <= 0:
                continue
            first = scenario.first_block[kind] + 2 * (index // scenario.per_cache[kind])
            writable.update((first, first + 1))
    return writable


def compress_unit(data):
    """(bytes, raw flag): the ZX02 stream, or the raw data if it would grow."""
    c = zx02.encode(data)
    return (data, True) if c is None else (c, False)


def compress_scenario(volume, disk, pic_records, music_records=()):
    """The compressed disk 2. `volume` is the patched 1,120-sector scenario
    volume; `pic_records` the picture records (or []). Returns (body, layout):
    body the full 1,440-sector disk image, layout the extra layout.json /
    assembler-define entries.

    Sectors 1..28 preserve blocks 0..6 (header, directory, code dictionary).
    Sectors 29..32 contain WZC3, counts, DATA/MESGS first blocks, then code
    entries (first block, length, sector, control) and message/data entries
    (sector, control). Control bits 0..6 give the byte offset in that sector;
    bit 7 marks raw storage. Units end at their decoded size. Writable raw
    blocks are aligned to sectors so SIO writes cannot touch adjacent units.
    The remaining arena holds code, data, messages, pictures and music.
    """
    writable = writable_data_blocks(disk)
    entry = disk.entry('SCENARIO.DATA')
    data_first = entry.first_block
    mesg_first = disk.entry('SCENARIO.MESGS').first_block
    code_entry = disk.entry('WIZARDRY.CODE')
    code = CodeFile(disk.read('WIZARDRY.CODE'))
    segs = sorted((code_entry.first_block + s.block, s.length) for s in code.segments)
    # Blocks 0-6 stay raw in place: the header/directory, plus the code file's
    # block 0, which no segment covers (it is never read, but a carried-over
    # volume must reconstruct byte for byte).
    map_start = MAP_START_SECTOR
    cursor = (map_start - 1 + 4) * 128
    body = bytearray(1440 * 128)
    body[:7 * 512] = volume[:7 * 512]

    def place(data, align=1):
        nonlocal cursor
        cursor = (cursor + align - 1) // align * align
        at = cursor
        cursor += len(data)
        if cursor > len(body):
            raise SystemExit('disk 2 is full: compressed content exceeds 1,440 sectors')
        body[at:cursor] = data
        return at

    def pack(data, writable=False):
        encoded, raw = (data, True) if writable else compress_unit(data)
        at = place(encoded, 128 if raw else 1)
        # The control byte is the byte offset in the first sector, plus
        # bit 7 for raw. Streams end at their decoded size; no sector padding.
        return at // 128 + 1, (0x80 if raw else 0) | (at % 128)

    code_entries = []
    for first_block, length in segs:
        nblk = -(-length // 512)
        start, ctl = pack(volume[first_block * 512:(first_block + nblk) * 512])
        code_entries.append((first_block, length, start, ctl))
    data_entries = [pack(volume[(data_first + i) * 512:(data_first + i + 1) * 512],
                         writable=i in writable) for i in range(116)]
    mesg_entries = [pack(volume[(mesg_first + i) * 512:(mesg_first + i + 1) * 512])
                   for i in range(15)]
    map_bytes = bytearray(MAP_MAGIC)
    map_bytes += bytes([len(segs), 116, 15])
    map_bytes += struct.pack('<HH', data_first, mesg_first)
    for first_block, length, start, ctl in code_entries:
        map_bytes += bytes([first_block]) + struct.pack('<HHB', length, start, ctl)
    for start, ctl in mesg_entries + data_entries:
        map_bytes += struct.pack('<HB', start, ctl)
    assert len(map_bytes) <= 4 * 128, len(map_bytes)
    body[(map_start - 1) * 128:(map_start - 1) * 128 + len(map_bytes)] = map_bytes
    map_code = 11
    map_mesg = map_code + 6 * len(segs)
    map_data = map_mesg + 3 * 15
    volume_end = cursor

    pic_offs, pic_ctl = [], []
    abs0 = None
    for rec in pic_records:
        if len(rec) > 1664:
            raise SystemExit('picture record exceeds the 1,664-byte runtime buffer')
        data, raw = compress_unit(rec)
        if not raw:
            data = struct.pack('<H', len(rec)) + data
        at = place(data)
        if abs0 is None:
            abs0 = at
        pic_offs.append(at - abs0)
        pic_ctl.append((0x8000 if raw else 0) | len(data))

    picture_end = cursor
    music_directory = []
    for song, address, image in music_records:
        at0 = cursor
        start, control = pack(image)
        music_directory.append({'song': song, 'sector': start, 'control': control,
                                'length': len(image), 'address': address,
                                'packed_bytes': cursor - at0})
    pics_base = abs0 // 128 + 1 if abs0 is not None else 1
    layout = {'MAP_START': map_start, 'MAP_SECTORS': 4, 'MAP_CODE': map_code,
              'MAP_DATA': map_data, 'MAP_MESG': map_mesg,
              'PICS_BASE': pics_base, 'PICS_BASE_OFF': abs0 - (pics_base - 1) * 128 if abs0 is not None else 0,
              'PICTURE_OFFS': pic_offs, 'PICTURE_LENS': pic_ctl,
              'VOLUME_BYTES': volume_end, 'PICTURE_END': picture_end, 'CONTENT_BYTES': cursor,
              'MUSIC_RECORDS': music_directory, 'CODEC': 'zx02'}
    return body, layout


def atr_scenario(path):
    """The scenario volume of an ATR from any build, as a PascalDisk. Volumes
    sit at a sector boundary; the scenario's directory (block 2) lists
    SCENARIO.DATA. A compressed disk 2 (with a 'WZC2' or 'WZC3'
    map after its directory) is decoded through the map first, so the volume
    reads as the ordinary Pascal volume it stands for."""
    from ucsd.disk import _DOS_ORDER
    body = Path(path).read_bytes()[16:]
    for start in range(0, len(body) - 280 * 512 + 1, 128):
        head = body[start + 1024:start + 1030]
        if head[:4] != bytes([0, 0, 6, 0]) or not 1 <= body[start + 1030] <= 7:
            continue
        reader = volume_blocks(body, start)
        image = bytearray(143360)
        for block in range(280):
            chunk = body[start + block * 512:start + (block + 1) * 512] if reader is None \
                else reader(block)
            track, index = divmod(block, 8)
            a, b = _DOS_ORDER[index]
            image[(track * 16 + a) * 256:(track * 16 + a + 1) * 256] = chunk[:256]
            image[(track * 16 + b) * 256:(track * 16 + b + 1) * 256] = chunk[256:]
        disk = PascalDisk(bytes(image), str(path))
        try:
            disk.entry('SCENARIO.DATA')
        except (KeyError, ValueError, FileNotFoundError):
            continue
        return disk
    raise SystemExit(f'{path}: no scenario volume found')


def volume_blocks(body, start):
    """A block -> 512-byte reader for a compressed scenario volume, or None if
    the volume at `start` is an ordinary raw one."""
    at = start + (MAP_START_SECTOR - 1) * 128
    magic = body[at:at + 4]
    if magic not in (b'WZC2', MAP_MAGIC):
        return None
    decode = zx02.decode if magic == MAP_MAGIC else compress.lzss_decode
    ncode, ndata, nmesg = body[at + 4:at + 7]
    data_first, mesg_first = struct.unpack('<HH', body[at + 7:at + 11])
    code_at = at + 11
    mesg_at = code_at + 6 * ncode
    data_at = mesg_at + 3 * nmesg

    def unit(off, ctl, size):
        chunk = body[start + (off - 1) * 128 + (ctl & 0x7F):]
        if ctl & 0x80:
            chunk = chunk[:size]
        return chunk if ctl & 0x80 else decode(chunk, size)

    segs = [(body[code_at + 6 * i],
             struct.unpack('<H', body[code_at + 6 * i + 1:code_at + 6 * i + 3])[0],
             struct.unpack('<H', body[code_at + 6 * i + 3:code_at + 6 * i + 5])[0],
             body[code_at + 6 * i + 5]) for i in range(ncode)]

    def read(block):
        at_b = start + 4 * block * 128           # the block's identity position
        if block < 7:
            return body[at_b:at_b + 512]
        if data_first <= block < data_first + ndata:
            e = data_at + 3 * (block - data_first)
            off, ctl = struct.unpack('<H', body[e:e + 2])[0], body[e + 2]
            return body[at_b:at_b + 512] if off == 0 and ctl == 0x80 else unit(off, ctl, 512)[:512]
        if mesg_first <= block < mesg_first + nmesg:
            e = mesg_at + 3 * (block - mesg_first)
            off, ctl = struct.unpack('<H', body[e:e + 2])[0], body[e + 2]
            return body[at_b:at_b + 512] if off == 0 and ctl == 0x80 else unit(off, ctl, 512)[:512]
        for fb, length, first, ctl in segs:
            if fb <= block < fb + -(-length // 512):
                # the whole padded block range, as it was encoded
                whole = unit(first, ctl, -(-length // 512) * 512)
                return whole[(block - fb) * 512:(block - fb + 1) * 512]
        raise AssertionError(f'block {block} is not in the map')
    return read


def open_scenario(path):
    return atr_scenario(path) if str(path).lower().endswith('.atr') else PascalDisk.open(path)


class TrimmedBoot:
    """The trimmed boot volume: its blocks in order, plus the directory entries."""
    def __init__(self, volume, entries):
        self.volume = volume
        self.entries = entries

    def block(self, n):
        return self.volume[n * 512:(n + 1) * 512]

    def entry(self, name):
        for e in self.entries:
            if e.name.upper() == name.upper():
                return e
        raise KeyError(name)

    def read(self, name):
        e = self.entry(name)
        return self.volume[e.first_block * 512:e.next_block * 512]


def trim_boot_volume(boot):
    """Trim the boot volume to what SYSTEM.STARTUP reads on the two-disk
    build: its own code, the title picture WT and SYSTEM.PASCAL (which
    EXITUTIL's FINDFILE looks up when the player leaves the utilities).
    Returns (the 76 blocks in block order, the kept entries)."""
    keep = ['SYSTEM.STARTUP', 'WT', 'SYSTEM.PASCAL']
    entries = [boot.entry(name) for name in keep]
    count = sum(e.next_block - e.first_block for e in entries)
    volume = bytearray((6 + count) * 512)
    volume[0:1024] = boot.block(0) + boot.block(1)
    d = boot.blocks(2, 4)
    volume[1024:1024 + 26] = d[0:26]
    struct.pack_into('<H', volume, 1024 + 16, len(entries))
    original = {e.name: 26 * (i + 1) for i, e in enumerate(boot.entries)}
    kept = []
    at = 6
    for i, e in enumerate(entries):
        slot = 1024 + 26 * (i + 1)
        src = original[e.name]
        volume[slot:slot + 26] = d[src:src + 26]
        struct.pack_into('<HH', volume, slot, at, at + e.next_block - e.first_block)
        volume[at * 512:(at + e.next_block - e.first_block) * 512] = \
            boot.blocks(e.first_block, e.next_block - e.first_block)
        kept.append(DirEntry(e.name, e.kind, at, at + e.next_block - e.first_block,
                             e.last_bytes, e.modified))
        at += e.next_block - e.first_block
    return volume, kept


def volume_bytes(disk):
    return bytearray(b''.join(disk.block(n) for n in range(280)))


def patch_volume(volume, disk, filename):
    """Apply the shared copy-protection patches to a code file inside a volume."""
    entry = disk.entry(filename)
    code = CodeFile(disk.read(filename))
    for seg_number, proc_number, offset, patch in patches.PATCHES[filename]:
        seg = code.segment(seg_number)
        proc = seg.procedure(proc_number)
        patches.patch_segment_code(seg.code, proc, offset, patch)      # validates the patch
        at = (entry.first_block + seg.block) * 512 + proc.enter + offset
        volume[at:at + len(patch)] = patch


def segment_rows(disk, filename):
    entry = disk.entry(filename)
    code = CodeFile(disk.read(filename))
    return {s.number: (entry.first_block + s.block, s.length) for s in code.segments}


def color_tables():
    """Lookup tables for src/color.s: Apple bytes to patterns of dot-pair classes.

    A dot pair's class depends on 4 dots (left neighbour, the pair, right
    neighbour): 1 white (a lit dot with a lit neighbour), 2 even-column hue
    (the left dot alone), 3 odd-column hue (the right dot alone), 0 black.
    A pattern packs 4 classes, leftmost in bits 7-6.
    """
    def pair_class(n0, a, b, n1):
        if (a and (n0 or b)) or (b and (a or n1)):
            return 1
        return 2 if a else 3 if b else 0

    def pattern(classes):
        v = 0
        for c in classes:
            v = v << 2 | c
        return v

    def dots(value, count):
        return [(value >> i) & 1 for i in range(count)]

    # class_a, page p (B's dots 7, 8) and index i (A's dots 0-6 << 1 | dot -1):
    # pairs 0-3 = dots (0,1) (2,3) (4,5) (6,7).
    class_a = []
    for page in range(4):
        for i in range(256):
            d = dots(i, 8) + dots(page, 2)          # dot -1, dots 0..6, dots 7, 8
            class_a.append(pattern([pair_class(*d[2 * k:2 * k + 4]) for k in range(4)]))
    # class_b, index i (B's dots 7-13 | dot 14 << 7): pairs 4-6, pixel 7 repeating 6.
    class_b = []
    for i in range(256):
        d = dots(i, 8)                              # dots 7..14
        c = [pair_class(*d[2 * k:2 * k + 4]) for k in range(3)]
        class_b.append(pattern(c + [c[2]]))

    def lone(v, parity):
        n = 0
        for i in range(parity, 7, 2):
            if v >> i & 1 and not (i > 0 and v >> (i - 1) & 1) and not (i < 6 and v >> (i + 1) & 1):
                n += 1
        return n

    def table(name, values):
        rows = [values[i:i + 32] for i in range(0, len(values), 32)]
        return [f'{name}:'] + ['        .byte ' + ', '.join(map(str, r)) for r in rows]

    lines = ['; Generated by build.py: colour classification tables.', '        .align 256']
    lines += table('class_a', class_a) + table('class_b', class_b)
    lines += table('lone_even', [lone(v & 0x7F, 0) for v in range(256)])
    lines += table('lone_odd', [lone(v & 0x7F, 1) for v in range(256)])
    return '\n'.join(lines) + '\n'


def tables_include(boot, scenario):
    """Segment tables for both programs and the boot volume's file list."""
    lines = ['; Generated by build.py.']
    for prefix, rows in [('startup', segment_rows(boot, 'SYSTEM.STARTUP')),
                         ('game', segment_rows(scenario, 'WIZARDRY.CODE'))]:
        for name, fn in [('block_lo', lambda b, n: b & 0xFF), ('block_hi', lambda b, n: b >> 8),
                         ('len_lo', lambda b, n: n & 0xFF), ('len_hi', lambda b, n: n >> 8)]:
            values = [fn(*rows[i]) if i in rows else 0 for i in range(32)]
            lines.append(f'{prefix}_{name}: .byte ' + ', '.join(str(v) for v in values))
    for name in ('seg_block_lo', 'seg_block_hi', 'seg_len_lo', 'seg_len_hi',
                 'seg_base_lo', 'seg_base_hi', 'seg_refs'):
        lines.append(f'{name}: .res 32, 0')
    # FOPEN on the boot volume: 16-byte Pascal name, first block, block count.
    lines.append('boot_files:')
    for e in boot.entries:
        name = bytes([len(e.name)]) + e.name.encode('ascii')
        lines.append('        .byte ' + ', '.join(str(b) for b in name.ljust(16, b'\0')))
        lines.append(f'        .word {e.first_block}, {e.next_block - e.first_block}')
    lines.append('        .byte 0')
    return '\n'.join(lines) + '\n'


HIGH = 0xB000
OVL = 0x6000
GOVL = 0x4000
LINKER_CONFIG = f"""
MEMORY {{
    MAIN: start = ${LOAD:04X}, size = $1906, file = "%O.main";
    HIGH: start = ${HIGH:04X}, size = $0A00, file = "%O.high";
    OVL:  start = ${OVL:04X}, size = $2000, file = "%O.ovl";
    GOVL: start = ${GOVL:04X}, size = $0B00, file = "%O.govl";
    MUS:  start = $C000, size = $0200, file = "%O.music";
    CMP:  start = $D800, size = $1000, file = "%O.comp";
}}
SEGMENTS {{
    CODE:   load = MAIN, type = rw;
    TABLES: load = HIGH, type = rw;
    OVERLAY: load = OVL, type = rw, align = $100;
    GAMEOVL: load = GOVL, type = rw;
    MUSIC:  load = MUS, type = rw;
    COMP:   load = CMP, type = rw, optional = yes;
}}
"""


def music_images(build):
    """The NES music for the disk (cached: running the NSF takes a while), or None."""
    import hashlib
    import pickle
    if ARGS.no_music or not NES_MUSIC.exists():
        return None
    key = hashlib.sha256(NES_MUSIC.read_bytes() + (HERE / 'music.py').read_bytes()).hexdigest()
    cache = build / 'music.cache'
    if cache.exists():
        cached = pickle.loads(cache.read_bytes())
        if cached[0] == key:
            return cached[1]
    images = music.music_images(NES_MUSIC, MUSIC_JINGLES, MUSIC_SLOT)
    cache.write_bytes(pickle.dumps((key, images)))
    return images


MUSIC_PLAYER, MUSIC_JINGLES, MUSIC_SLOT = 0xC000, 0xC200, 0xD800


def picture_images(build, scenario):
    """The redrawn pictures for the disk (cached), or None for the Apple's own:
    (disk records, picture of each monster, chest, gold, chest sum, gold sum)."""
    import pickle
    from wizardry_scenario import Scenario
    data = Scenario(scenario)
    if ARGS.pictures == 'apple' or not pictures.available(data):
        if ARGS.pictures not in (None, 'apple'):
            raise SystemExit('the sprites are missing: python3 port/atari/pictures.py --fetch')
        return None
    mode = ARGS.pictures or 'monster'
    key = pictures.cache_key(data, mode)
    cache = build / 'pictures.cache'            # the last few sets: the test images use two scenarios
    cached = pickle.loads(cache.read_bytes()) if cache.exists() else {}
    if key not in cached:
        converted, of_monster, chest, gold, chest_sum, gold_sum, _ = pictures.picture_set(data, mode)
        cached[key] = ([p.image() for p in converted], of_monster, chest, gold, chest_sum, gold_sum)
        while len(cached) > 4:
            del cached[next(iter(cached))]
        cache.write_bytes(pickle.dumps(cached))
    return cached[key]


def picture_starts(pics):
    """Each picture's first sector, counted from PICS_SECTOR."""
    starts, at = [], 0
    for record in pics[0]:
        starts.append(at)
        at += sectors(record)
    return starts


def assemble(build, layout, images, song_sectors, pics, boot, pic_table):
    """Assemble and link with the given disk layout; return the parts."""
    (HERE / 'src/segtab.inc').write_text(tables_include(boot, open_scenario(ARGS.scenario)))
    (HERE / 'src/color_tables.inc').write_text(color_tables())
    if images:
        cues = twodisk_music.cue_include(images, MUSIC_DIRECTORY) if ARGS.disk2 else music.cue_include(images[1], song_sectors)
        (HERE / 'src/music_cues.inc').write_text(cues)
    if pics:
        (HERE / 'src/picture_tables.inc').write_text(pictures.tables_include(*pics[1:], pic_table))
    config = LINKER_CONFIG
    if ARGS.disk2:
        config = config.replace('MUS:  start = $C000', 'MUS:  start = $E600')
        config = config.replace('CMP:  start = $D800, size = $1000', 'CMP:  start = $C900, size = $0700')
    (build / 'wizardry.cfg').write_text(config)
    defines = ((['-D', 'TRACE'] if ARGS.trace else []) + (['-D', 'TESTMODE_ON'] if ARGS.testmode else []) +
               (['-D', 'NO_TITLE'] if ARGS.no_title else []))
    for name, value in layout.items():
        defines += ['-D', f'{name}={value}']
    defines += ['-D', f'MUSIC_PRESENT={int(images is not None)}',
                '-D', f'PARTY_PRESENT={int(ARGS.party)}',
                '-D', f'MUSA_PAGES={(layout["MUSA_SECTORS"] + 1) // 2}',
                '-D', f'OPEN_PAGES={(layout["OPEN_SECTORS"] + 1) // 2}',
                '-D', f'SPRITES_PRESENT={int(pics is not None)}', '-D', f'SPRITE_LIT={pictures.LIT}']
    subprocess.run([TOOLCHAIN / 'ca65', '-g', *defines, '-I', HERE / 'src', '-o', build / 'main.o',
                    HERE / 'src/main.s'], check=True)
    subprocess.run([TOOLCHAIN / 'ld65', '-C', build / 'wizardry.cfg', '-Ln', build / 'labels.txt',
                    '-o', build / 'wizardry.bin', build / 'main.o'], check=True)
    return ((build / 'wizardry.bin.main').read_bytes(), (build / 'wizardry.bin.high').read_bytes(),
            (build / 'wizardry.bin.ovl').read_bytes(), (build / 'wizardry.bin.govl').read_bytes(),
            (build / 'wizardry.bin.music').read_bytes(), (build / 'wizardry.bin.comp').read_bytes())


def sectors(data):
    return -(-len(data) // 128)


def pad(data):
    return data + bytes(sectors(data) * 128 - len(data))


def write_atr(path, body):
    paragraphs = len(body) // 16
    header = struct.pack('<HHHBxxxxxxxxx', 0x0296, paragraphs & 0xFFFF, 128, paragraphs >> 16)
    assert len(header) == 16 and len(body) % 128 == 0
    path.write_bytes(header + bytes(body))


def main():
    global MUSIC_DIRECTORY
    build = HERE / 'build'
    build.mkdir(exist_ok=True)
    boot, scenario = PascalDisk.open(BOOT), open_scenario(ARGS.scenario)
    party_members = []
    if ARGS.party:
        scenario, party_members = party.seed(scenario)
        (HERE / 'src/party_tables.inc').write_text(party.tables_include(scenario, party_members))
    if ARGS.disk2:
        boot = TrimmedBoot(*trim_boot_volume(boot))
    boot_volume = boot.volume if ARGS.disk2 else volume_bytes(boot)
    scenario_volume = volume_bytes(scenario)
    patch_volume(boot_volume, boot, 'SYSTEM.STARTUP')
    if not ARGS.disk2:
        patch_volume(boot_volume, boot, 'WIZARDRY.CODE')
    patch_volume(scenario_volume, scenario, 'WIZARDRY.CODE')
    # Pass 1 measures the code; pass 2 assembles with the final disk layout.
    images = music_images(build)
    if ARGS.disk2 and images:
        images = twodisk_music.relocate_images(images)
    pics = picture_images(build, scenario)
    pics_data = b''.join(pics[0]) if pics else b''
    layout_c, cmp_extra = {}, {}
    MUSIC_DIRECTORY = []
    if ARGS.disk2 and (pics or images):
        # The compressed disk 2 does not depend on the assembly: build it once.
        pic_recs = pics[0] if pics else []
        disk2_body, cmp_layout = compress_scenario(scenario_volume, scenario, pic_recs, twodisk_music.records(images) if images else ())
        sectors_, skips = [], []
        for off in cmp_layout['PICTURE_OFFS']:
            byte = cmp_layout['PICS_BASE_OFF'] + off
            sectors_.append(cmp_layout['PICS_BASE'] + byte // 128)
            skips.append(byte % 128)
        pic_table = {'sector': sectors_, 'skip': skips,
                     'len': [(l & 0xFF, l >> 8) for l in cmp_layout['PICTURE_LENS']]}
        MUSIC_DIRECTORY = cmp_layout['MUSIC_RECORDS']
        layout_c = {k: v for k, v in cmp_layout.items() if isinstance(v, int)}
        layout_c['SCENCMP'] = 1
        if pics:
            layout_c['PICSCMP'] = 1
        cmp_extra = {k: v for k, v in cmp_layout.items() if not isinstance(v, int)}
    else:
        disk2_body = scenario_volume
        pic_table = {'sector': [f'PICS_SECTOR+{s}' for s in picture_starts(pics)]} if pics else {}
    layout = {'BOOT_SECTORS': 1, 'TABLE_SECTOR': 1, 'TABLE_SECTORS': 1, 'OVL_SECTOR': 1, 'OVL_SECTORS': 1,
              'GOVL_SECTOR': 1, 'GOVL_SECTORS': 1, 'MUSA_SECTOR': 1, 'MUSA_SECTORS': 1,
              'OPEN_SECTOR': 1, 'OPEN_SECTORS': 1, 'COMP_SECTOR': 1, 'COMP_SECTORS': 1, 'PICS_SECTOR': 1, 'BOOTVOL': 1, 'SCENVOL': 1}
    if ARGS.disk2:
        layout['DISK2'] = 1
        layout.update(layout_c)
    song_sectors = {}
    for _ in range(2):
        code, tables, overlay, game_overlay, player, decoder = assemble(build, layout, images, song_sectors, pics, boot, pic_table)
        ovl_sector = sectors(code) + sectors(tables) + 1
        govl_sector = ovl_sector + sectors(overlay)
        # Music: the player and jingles (for $C000), then each song (for the slot).
        musa = (player if ARGS.disk2 else player.ljust(MUSIC_JINGLES - MUSIC_PLAYER, b'\0') + images[0]) if images else b''
        songs = [(s, img) for s, img in sorted(images[2].items())] if images and not ARGS.disk2 else []
        comp_sector = govl_sector + sectors(game_overlay)
        sector = comp_sector + sectors(decoder) + sectors(musa)
        song_sectors = {}
        for s, img in songs:
            song_sectors[s] = (sector, sectors(img))
            sector += sectors(img)
        layout = {'BOOT_SECTORS': sectors(code), 'TABLE_SECTOR': sectors(code) + 1,
                  'TABLE_SECTORS': sectors(tables), 'OVL_SECTOR': ovl_sector, 'OVL_SECTORS': sectors(overlay),
                  'GOVL_SECTOR': govl_sector, 'GOVL_SECTORS': sectors(game_overlay),
                  'COMP_SECTOR': comp_sector, 'COMP_SECTORS': sectors(decoder),
                  'MUSA_SECTOR': comp_sector + sectors(decoder), 'MUSA_SECTORS': max(1, sectors(musa)),
                  'OPEN_SECTOR': song_sectors.get(music.OPENING, (1, 1))[0],
                  'OPEN_SECTORS': song_sectors.get(music.OPENING, (1, 1))[1],
                  # disk 2: the pictures live on the scenario disk; the boot volume
                  # follows the runtime directly
                  'PICS_SECTOR': sector, 'BOOTVOL': sector if ARGS.disk2 else sector + sectors(pics_data),
                  'SCENVOL': 1 if ARGS.disk2 else sector + sectors(pics_data) + 1120}
        if ARGS.disk2:
            layout.update(layout_c)
            layout['DISK2'] = 1
    assert code[1] == layout['BOOT_SECTORS'] and sectors(code) < 256
    if images and ARGS.disk2:
        assert len(player) <= 512
        assert twodisk_music.JINGLES + len(images[0]) <= twodisk_music.PLAYER
        assert twodisk_music.SLOT + max(map(len, images[2].values())) <= 0xFFFA
    elif images:
        assert len(player) <= MUSIC_JINGLES - MUSIC_PLAYER, 'the music player overlaps the jingles'
        assert MUSIC_JINGLES + len(images[0]) <= 0xD000, 'the jingles run into the I/O area'
        assert len(musa) <= 0x2000 and max(len(img) for _, img in songs) <= 0x2000, 'read to $4000-$5FFF first'
        assert MUSIC_SLOT + max(len(img) for _, img in songs) <= 0xFFFA, 'a song is too long for the slot'
    runtime = pad(code) + pad(tables) + pad(overlay) + pad(game_overlay) + pad(decoder)
    base = ARGS.out[:-4] if ARGS.out.endswith('.atr') else ARGS.out
    if ARGS.disk2:
        body1 = runtime + pad(musa) + b''.join(pad(img) for _, img in songs) + boot_volume
        if len(body1) > 1440 * 128 or len(disk2_body) > 1440 * 128:
            raise SystemExit('two-disk build exceeds 1,440 sectors per disk')
        write_atr(build / f'{base}_disk1.atr', body1)
        write_atr(build / f'{base}_disk2.atr', disk2_body)
    else:
        write_atr(build / ARGS.out, runtime + pad(musa)
                  + b''.join(pad(img) for _, img in songs) + pics_data + boot_volume + scenario_volume)
    extra = {'SPRITES': 0, 'MUSIC': int(images is not None)}
    if pics:
        extra = {'SPRITES': 1, 'PICTURES': ARGS.pictures or 'monster', 'MUSIC': int(images is not None)}
        extra.update(pic_table if ARGS.disk2 else
                     {'PICTURE_STARTS': picture_starts(pics),
                      'PICTURE_SECS': [sectors(r) for r in pics[0]]})
    if party_members:
        extra['PARTY'] = party_members
        extra['PARTY_AUTOFORM'] = 1
    if ARGS.disk2:
        extra.update(cmp_extra)
        extra.update({'COMP_ADDR': 0xC900, 'PICOUT': 0xC280, 'MUSIC_PLAYER': twodisk_music.PLAYER,
                      'MUSIC_SLOT': twodisk_music.SLOT, 'MUSIC_JINGLES': twodisk_music.JINGLES})
        extra['DISKS'] = [
            {'file': f'{base}_disk1.atr', 'role': 'program', 'volbase': layout['BOOTVOL'],
             'files': ['SYSTEM.STARTUP', 'WT', 'SYSTEM.PASCAL']},
            {'file': f'{base}_disk2.atr', 'role': 'scenario', 'volbase': 1,
             'files': ['WIZARDRY.CODE', 'SCENARIO.DATA', 'SCENARIO.MESGS']}]
    manifest = json.dumps({**layout, **extra}, indent=2) + '\n'
    (build / 'layout.json').write_text(manifest)
    stems = (f'{base}_disk1', f'{base}_disk2') if ARGS.disk2 else (base,)
    for stem in stems:
        (build / f'{stem}.layout.json').write_text(manifest)
        (build / f'{stem}.labels.txt').write_text((build / 'labels.txt').read_text())
    if party_members:
        print('OP party formed at startup: ' + ', '.join(member['name'] for member in party_members))
    if ARGS.disk2:
        d1 = len(body1) // 128
        d2 = len(disk2_body) // 128
        print(f'{base}_disk1.atr: {d1} sectors ({len(body1) + 16} bytes, {1440 - d1} spare); '
              f'{base}_disk2.atr: {d2} sectors ({len(disk2_body) + 16} bytes), '
              f'{len(pics[0]) if pics else 0} picture records'
              + (f', {1440 * 128 - layout["CONTENT_BYTES"]} bytes spare' if layout.get('SCENCMP') else f', {1440 - d2} sectors spare'))
    else:
        print(f'{ARGS.out}: boot {layout["BOOT_SECTORS"]} sectors (code ${LOAD:04X}-${LOAD + len(code) - 1:04X}), '
              f'high {layout["TABLE_SECTORS"]} sectors (${HIGH:04X}-${HIGH + len(tables) - 1:04X}), '
              f'overlay {layout["OVL_SECTORS"]} sectors (${OVL:04X}-${OVL + len(overlay) - 1:04X}), '
              f'game overlay {layout["GOVL_SECTORS"]} sectors (${GOVL:04X}-${GOVL + len(game_overlay) - 1:04X}), '
              f'music {sector - layout["MUSA_SECTOR"] if images else 0} sectors ({len(songs)} songs), '
              f'pictures {sectors(pics_data)} sectors ({len(pics[0]) if pics else 0}), '
              f'boot volume from sector {layout["BOOTVOL"]}, scenario volume from {layout["SCENVOL"]}; '
              f'{layout["SCENVOL"] - 1 + 1120} sectors in all{" (no title)" if ARGS.no_title else ""}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--scenario', default=PROJECT / 'appleII/images/wizardry_i/snafaru_restored_scenario.dsk',
                        help='scenario disk: an Apple .dsk, or an .atr from an earlier build (keeps its characters)')
    parser.add_argument('--out', default='wizardry.atr', help='output file name in build/')
    parser.add_argument('--no-music', action='store_true', help='leave out the NES music')
    parser.add_argument('--party', action='store_true',
                        help='add and automatically form six level-50 characters: 999 HP, '
                             'max attributes, 1,000,000 gold each, all spells, no equipment/passwords')
    parser.add_argument('--disk2', action='store_true',
                        help='two disks within the 180 KB budget: a program disk (runtime and trimmed '
                             'boot volume) and a scenario disk (compressed game and PCE pictures); '
                             'gameplay music is included when its NSF is available; --no-music omits it')
    parser.add_argument('--pictures', choices=['class', 'monster', 'apple'],
                        help="the monster pictures: redrawn, one per monster (monster: the default with the "
                             "sprites in art/pce/); redrawn, one per kind of monster as on the Apple, so that a "
                             "picture tells no more than the unidentified name (class); or the Apple's own (apple)")
    parser.add_argument('--no-title', action='store_true',
                        help='start straight in the game, skipping SYSTEM.STARTUP (lockstep tests)')
    parser.add_argument('--trace', action='store_true', help='record executed instructions at $4000')
    parser.add_argument('--testmode', action='store_true',
                        help='key waits stir the RNG by a harness-set amount (lockstep tests)')
    parser.add_argument('--test-images', action='store_true',
                        help='build test.atr, played.atr (test mode, no title) and title.atr for the tests')
    ARGS = parser.parse_args()
    if ARGS.test_images:
        if ARGS.disk2:
            ARGS.out, ARGS.testmode, ARGS.no_title, ARGS.pictures = 'test.atr', True, False, 'apple'
            main()
        else:
            played = PROJECT / 'appleII/images/wizardry_i/wizardry_i_scenario.dsk'
            for out, testmode, no_title, scenario in [('test.atr', True, True, ARGS.scenario),
                                                      ('played.atr', True, True, played),
                                                      ('title.atr', False, False, ARGS.scenario)]:
                ARGS.out, ARGS.testmode, ARGS.no_title, ARGS.scenario = out, testmode, no_title, scenario
                main()
    else:
        main()
