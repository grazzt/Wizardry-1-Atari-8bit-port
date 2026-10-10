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
from ucsd.disk import PascalDisk                        # noqa: E402
from pvm import patches                                  # noqa: E402
import music                                             # noqa: E402
import pictures                                          # noqa: E402

TOOLCHAIN = PROJECT / 'tools/toolchain/local/bin'
LOAD = 0x06FA             # boot header; code proper starts at $0700

BOOT = PROJECT / 'appleII/images/wizardry_i/wizardry_i_boot.dsk'
# The NES version's music (an NSF rip, kept out of Git): played on the title.
NES_MUSIC = PROJECT / 'nes/snafaru/wiz1.nsf'


def atr_scenario(path):
    """The scenario volume of an ATR from any build, as a PascalDisk. Volumes
    sit at a sector boundary; the scenario's directory (block 2) lists
    SCENARIO.DATA."""
    from ucsd.disk import _DOS_ORDER
    body = Path(path).read_bytes()[16:]
    for start in range(0, len(body) - 280 * 512 + 1, 128):
        head = body[start + 1024:start + 1030]
        if head[:4] != bytes([0, 0, 6, 0]) or not 1 <= body[start + 1030] <= 7:
            continue
        image = bytearray(143360)
        for block in range(280):
            chunk = body[start + block * 512:start + (block + 1) * 512]
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


def open_scenario(path):
    return atr_scenario(path) if str(path).lower().endswith('.atr') else PascalDisk.open(path)


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
}}
SEGMENTS {{
    CODE:   load = MAIN, type = rw;
    TABLES: load = HIGH, type = rw;
    OVERLAY: load = OVL, type = rw, align = $100;
    GAMEOVL: load = GOVL, type = rw;
    MUSIC:  load = MUS, type = rw;
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


def assemble(build, layout, images, song_sectors, pics):
    """Assemble and link with the given disk layout; return the parts."""
    (HERE / 'src/segtab.inc').write_text(tables_include(PascalDisk.open(BOOT), open_scenario(ARGS.scenario)))
    (HERE / 'src/color_tables.inc').write_text(color_tables())
    if images:
        (HERE / 'src/music_cues.inc').write_text(music.cue_include(images[1], song_sectors))
    if pics:
        (HERE / 'src/picture_tables.inc').write_text(pictures.tables_include(*pics[1:], picture_starts(pics)))
    (build / 'wizardry.cfg').write_text(LINKER_CONFIG)
    defines = ((['-D', 'TRACE'] if ARGS.trace else []) + (['-D', 'TESTMODE_ON'] if ARGS.testmode else []) +
               (['-D', 'NO_TITLE'] if ARGS.no_title else []))
    for name, value in layout.items():
        defines += ['-D', f'{name}={value}']
    defines += ['-D', f'MUSIC_PRESENT={int(images is not None)}',
                '-D', f'MUSA_PAGES={(layout["MUSA_SECTORS"] + 1) // 2}',
                '-D', f'OPEN_PAGES={(layout["OPEN_SECTORS"] + 1) // 2}',
                '-D', f'SPRITES_PRESENT={int(pics is not None)}', '-D', f'SPRITE_LIT={pictures.LIT}']
    subprocess.run([TOOLCHAIN / 'ca65', '-g', *defines, '-I', HERE / 'src', '-o', build / 'main.o',
                    HERE / 'src/main.s'], check=True)
    subprocess.run([TOOLCHAIN / 'ld65', '-C', build / 'wizardry.cfg', '-Ln', build / 'labels.txt',
                    '-o', build / 'wizardry.bin', build / 'main.o'], check=True)
    return ((build / 'wizardry.bin.main').read_bytes(), (build / 'wizardry.bin.high').read_bytes(),
            (build / 'wizardry.bin.ovl').read_bytes(), (build / 'wizardry.bin.govl').read_bytes(),
            (build / 'wizardry.bin.music').read_bytes())


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
    build = HERE / 'build'
    build.mkdir(exist_ok=True)
    boot, scenario = PascalDisk.open(BOOT), open_scenario(ARGS.scenario)
    boot_volume, scenario_volume = volume_bytes(boot), volume_bytes(scenario)
    patch_volume(boot_volume, boot, 'SYSTEM.STARTUP')
    patch_volume(boot_volume, boot, 'WIZARDRY.CODE')
    patch_volume(scenario_volume, scenario, 'WIZARDRY.CODE')
    # Pass 1 measures the code; pass 2 assembles with the final disk layout.
    images = music_images(build)
    pics = picture_images(build, scenario)
    pics_data = b''.join(pics[0]) if pics else b''
    layout = {'BOOT_SECTORS': 1, 'TABLE_SECTOR': 1, 'TABLE_SECTORS': 1, 'OVL_SECTOR': 1, 'OVL_SECTORS': 1,
              'GOVL_SECTOR': 1, 'GOVL_SECTORS': 1, 'MUSA_SECTOR': 1, 'MUSA_SECTORS': 1,
              'OPEN_SECTOR': 1, 'OPEN_SECTORS': 1, 'PICS_SECTOR': 1, 'BOOTVOL': 1, 'SCENVOL': 1}
    song_sectors = {}
    for _ in range(2):
        code, tables, overlay, game_overlay, player = assemble(build, layout, images, song_sectors, pics)
        ovl_sector = sectors(code) + sectors(tables) + 1
        govl_sector = ovl_sector + sectors(overlay)
        # Music: the player and jingles (for $C000), then each song (for the slot).
        musa = player.ljust(MUSIC_JINGLES - MUSIC_PLAYER, b'\0') + images[0] if images else b''
        songs = [(s, img) for s, img in sorted(images[2].items())] if images else []
        sector = govl_sector + sectors(game_overlay) + sectors(musa)
        song_sectors = {}
        for s, img in songs:
            song_sectors[s] = (sector, sectors(img))
            sector += sectors(img)
        layout = {'BOOT_SECTORS': sectors(code), 'TABLE_SECTOR': sectors(code) + 1,
                  'TABLE_SECTORS': sectors(tables), 'OVL_SECTOR': ovl_sector, 'OVL_SECTORS': sectors(overlay),
                  'GOVL_SECTOR': govl_sector, 'GOVL_SECTORS': sectors(game_overlay),
                  'MUSA_SECTOR': govl_sector + sectors(game_overlay), 'MUSA_SECTORS': max(1, sectors(musa)),
                  'OPEN_SECTOR': song_sectors.get(music.OPENING, (1, 1))[0],
                  'OPEN_SECTORS': song_sectors.get(music.OPENING, (1, 1))[1],
                  'PICS_SECTOR': sector, 'BOOTVOL': sector + sectors(pics_data),
                  'SCENVOL': sector + sectors(pics_data) + 1120}
    assert code[1] == layout['BOOT_SECTORS'] and sectors(code) < 256
    if images:
        assert len(player) <= MUSIC_JINGLES - MUSIC_PLAYER, 'the music player overlaps the jingles'
        assert MUSIC_JINGLES + len(images[0]) <= 0xD000, 'the jingles run into the I/O area'
        assert len(musa) <= 0x2000 and max(len(img) for _, img in songs) <= 0x2000, 'read to $4000-$5FFF first'
        assert MUSIC_SLOT + max(len(img) for _, img in songs) <= 0xFFFA, 'a song is too long for the slot'
    write_atr(build / ARGS.out, pad(code) + pad(tables) + pad(overlay) + pad(game_overlay) + pad(musa)
              + b''.join(pad(img) for _, img in songs) + pics_data + boot_volume + scenario_volume)
    extra = {'SPRITES': 0}
    if pics:
        extra = {'SPRITES': 1, 'PICTURES': ARGS.pictures or 'monster', 'PICTURE_STARTS': picture_starts(pics)}
    (build / 'layout.json').write_text(json.dumps({**layout, **extra}, indent=2) + '\n')
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
        played = PROJECT / 'appleII/images/wizardry_i/wizardry_i_scenario.dsk'
        for out, testmode, no_title, scenario in [('test.atr', True, True, ARGS.scenario),
                                                  ('played.atr', True, True, played),
                                                  ('title.atr', False, False, ARGS.scenario)]:
            ARGS.out, ARGS.testmode, ARGS.no_title, ARGS.scenario = out, testmode, no_title, scenario
            main()
    else:
        main()
