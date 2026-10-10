"""Monster and treasure pictures redrawn for the Atari.

    python3 port/atari/pictures.py --fetch            download the sprites (once)
    python3 port/atari/pictures.py --sheet OUT.png    preview every picture

The Apple pictures are 70x50 line drawings, mostly white. With the sprites
in art/pce/ (Jun Suemi's monsters as drawn for the PC Engine version, 64x96
each; not in Git), build.py replaces them: each sprite is converted to what
the Atari can show in the picture box and stored on the disk.

The Atari display (src/picture.s): the mode F bitmap, black and white (at
luminance LIT), with players and missiles in front as five strips of eight
cells; a cell is one colour clock, 2 hi-res pixels. Under a set player bit
an unlit pixel shows the player's colour and a lit pixel the player's hue at
luminance LIT. Each strip takes a new colour every BAND lines. So a cell is
either black/white or dark/light of its strip's hue, and the converter picks
the strip colours, the cells and then the pixels (error diffusion between
each cell's two colours).

Which sprite a monster gets: its own (mode 'monster', the default), or one
per (unidentified name, Apple picture number), the sprite of the first
monster of that kind (mode 'class'). The Apple has 20 pictures for its 101
monsters, so there a picture tells no more than the unidentified name does;
'class' keeps that, while 'monster' shows what the monster is before the
party has identified it. The chest and the gold are the Apple pictures,
tinted.

A picture on disk: one sector with the first screen line, the line count,
the 5 x 19 strip colours and a flag per band ($80 where a colour changes, so
the Atari needs an interrupt there), then sectors of 8 lines, a line being
11 bitmap bytes (screen bytes 1-11) and the 5 strips' player bytes.
"""
import argparse
import hashlib
import json
import struct
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
sys.path.insert(0, str(PROJECT / 'tools'))

from wizardry_scenario import Scenario, pstring                 # noqa: E402

ART = PROJECT / 'art/pce'
WIKI = 'https://wizardry.wiki.gg/images/PCECD_MS_{}.png'
PALETTE = HERE / 'atari800_ntsc.json'       # Atari800's NTSC palette (harness.py palette())

LIT = 0x0C                          # COLOR1 in the game when the sprites are there
TOP, LINES, BAND = 6, 76, 4         # screen lines 6-81 in 19 bands
LEFT, WIDTH = 10, 80                # hi-res x 10-89: the five strips
BYTE0, BYTES = 1, 11                # bitmap bytes 1-11 of each line (x 8-95)
STRIPS, CELLS, BANDS = 5, 8, LINES // BAND
NOISE = 0.15                        # weight of dither noise when choosing colours
CHEST, GOLD = 18, 19                # Apple picture numbers (REWARDS)
TINT = {CHEST: 0x32, GOLD: 0x26}    # player colours for the two Apple pictures

# Scenario monster name -> sprite, where the plain rule (below) does not give it.
SPRITE_NAMES = {'BUSHWACKER': 'Bushwhacker', 'LVL 3 SAMURAI': 'Lvl5 Samurai', 'MASTER NINJA': 'Master Ninja A',
                'THE HIGH MASTER': 'High Master', 'W E R D N A': 'Werdna', "WILL O' WISP": "Will o' Wisp",
                "MURPHY'S GHOST": "Murphy's Ghost", 'CREEPING COIN?': 'Creeping Coin'}


def sprite_name(monster):
    if monster in SPRITE_NAMES:
        return SPRITE_NAMES[monster]
    return ' '.join(w.capitalize() for w in monster.replace('LVL ', 'LVL').split())


def monsters(scenario):
    """(unidentified name, name, Apple picture) of every monster."""
    out = []
    for i in range(scenario.on_disk['ZENEMY']):
        r = scenario.record('ZENEMY', i)
        out.append((pstring(r, 0, 15), pstring(r, 32, 15), struct.unpack_from('<h', r, 64)[0]))
    return out


def sprite_path(name):
    return ART / (name.replace(' ', '_') + '.png')


def fetch(scenario):
    ART.mkdir(parents=True, exist_ok=True)
    for name in sorted({sprite_name(m[1]) for m in monsters(scenario)}):
        path = sprite_path(name)
        if path.exists():
            continue
        url = WIKI.format(urllib.parse.quote(name.replace(' ', '_')))
        request = urllib.request.Request(url, headers={'User-Agent': 'wizardry-atari-port build script'})
        with urllib.request.urlopen(request) as response:
            path.write_bytes(response.read())
        print(f'{path.name}: {path.stat().st_size} bytes')


def available(scenario):
    return ART.is_dir() and all(sprite_path(sprite_name(m[1])).exists() for m in monsters(scenario))


# --- conversion ----------------------------------------------------------------------

PAL = np.array(json.loads(PALETTE.read_text()), dtype=float) if PALETTE.exists() else None
WEIGHT = np.array([0.30, 0.59, 0.11]) ** 0.5 * 1.7
COLOURS = [h << 4 | l for h in range(16) for l in range(0, 16, 2)]


def lit_colour(c):
    return c & 0xF0 | LIT


def pair_error(t, dark, lit):
    """Error of showing colours t (n, 3) by dithering dark/lit (k, 3 each): (k, n).
    The distance to the segment between them, plus the noise the dither makes."""
    d = (lit - dark) * WEIGHT                            # (k, 3)
    v = (t[None, :, :] - dark[:, None, :]) * WEIGHT      # (k, n, 3)
    dd = np.maximum((d * d).sum(axis=1), 1e-9)[:, None]  # (k, 1)
    u = np.clip((v * d[:, None, :]).sum(axis=2) / dd, 0, 1)
    r = v - u[:, :, None] * d[:, None, :]
    return (r * r).sum(axis=2) + NOISE * u * (1 - u) * dd


def choose(canvas):
    """Strip colours and covered cells for a LINES x WIDTH canvas: (error, colours, cover)."""
    colours = np.zeros((STRIPS, BANDS), dtype=int)
    cover = np.zeros((LINES, WIDTH // 2), dtype=bool)
    dark = PAL[COLOURS]
    lit = PAL[[lit_colour(c) for c in COLOURS]]
    total = 0.0
    for s in range(STRIPS):
        for b in range(BANDS):
            t = canvas[b * BAND:(b + 1) * BAND, s * 16:(s + 1) * 16].reshape(-1, 3)
            if not t.any():
                continue
            mono = pair_error(t, PAL[[0]], PAL[[LIT]]).reshape(-1, 2).sum(axis=1)       # per cell
            e = pair_error(t, dark, lit).reshape(len(COLOURS), -1, 2).sum(axis=2)
            totals = np.minimum(e, mono).sum(axis=1)
            i = int(totals.argmin())
            total += totals[i]
            cov = (e[i] < mono).reshape(BAND, CELLS)
            if cov.any():
                colours[s, b] = COLOURS[i]
                cover[b * BAND:(b + 1) * BAND, s * CELLS:(s + 1) * CELLS] = cov
    return total, colours, cover


def cell_colours(colours, cover):
    """Each pixel's unlit and lit colour register values: two LINES x WIDTH arrays."""
    per_cell = np.repeat(np.repeat(colours.T, BAND, axis=0), CELLS, axis=1)             # LINES x 40
    unlit = np.where(cover, per_cell, 0)
    lit = np.where(cover, per_cell & 0xF0 | LIT, LIT)
    return np.repeat(unlit, 2, axis=1), np.repeat(lit, 2, axis=1)


def diffuse(canvas, unlit, lit):
    """The lit pixels: serpentine error diffusion between each pixel's two colours."""
    work = canvas.copy()
    bits = np.zeros((LINES, WIDTH), dtype=bool)
    a_rgb, b_rgb = PAL[unlit], PAL[lit]
    for y in range(LINES):
        step = 1 if y % 2 == 0 else -1
        for x in (range(WIDTH) if step == 1 else range(WIDTH - 1, -1, -1)):
            t = work[y, x]
            a, b = a_rgb[y, x], b_rgb[y, x]
            on = (((t - b) * WEIGHT) ** 2).sum() < (((t - a) * WEIGHT) ** 2).sum()
            bits[y, x] = on
            err = (t - (b if on else a)) * 0.75
            if 0 <= x + step < WIDTH:
                work[y, x + step] += err * 7 / 16
            if y + 1 < LINES:
                if 0 <= x - step < WIDTH:
                    work[y + 1, x - step] += err * 3 / 16
                work[y + 1, x] += err * 5 / 16
                if 0 <= x + step < WIDTH:
                    work[y + 1, x + step] += err / 16
    return bits


class Picture:
    """bits (LINES x WIDTH), cover (LINES x 40 cells), colours (STRIPS x BANDS)."""

    def __init__(self, bits, cover, colours):
        self.bits, self.cover, self.colours = bits, cover, colours.copy()
        # A strip with no cell in a band keeps its colour: fewer changes, fewer interrupts.
        for s in range(STRIPS):
            used = [cover[b * BAND:(b + 1) * BAND, s * CELLS:(s + 1) * CELLS].any() for b in range(BANDS)]
            if any(used):
                last = self.colours[s, used.index(True)]
                for b in range(BANDS):
                    if used[b]:
                        last = self.colours[s, b]
                    self.colours[s, b] = last
        self.changes = [b == 0 or bool((self.colours[:, b] != self.colours[:, b - 1]).any()) for b in range(BANDS)]
        rows = np.nonzero(bits.any(axis=1) | cover.any(axis=1))[0]
        self.first, self.height = int(rows[0]), int(rows[-1] - rows[0] + 1)

    def rgb(self):
        """What the Atari shows at screen lines TOP.., x LEFT..: LINES x WIDTH x 3."""
        unlit, lit = cell_colours(self.colours, self.cover)
        return PAL[np.where(self.bits, lit, unlit)].astype(np.uint8)

    def line_bytes(self, y):
        """Bitmap bytes BYTE0.. and the five strips' player bytes of canvas line y."""
        row = np.zeros(BYTES * 8, dtype=bool)
        row[LEFT - 8 * BYTE0:LEFT - 8 * BYTE0 + WIDTH] = self.bits[y]
        out = bytearray(np.packbits(row).tobytes())
        for s in range(STRIPS):
            cells = self.cover[y, s * CELLS:(s + 1) * CELLS]
            if s < 4:
                out.append(int(np.packbits(cells)[0]))
            else:               # missiles 0-3 left to right: bits 1,0  3,2  5,4  7,6
                out.append(sum(1 << (i ^ 1) for i in range(8) if cells[i]))
        return bytes(out)

    def image(self):
        """The disk record."""
        head = bytearray(128)
        head[0], head[1] = TOP + self.first, self.height
        head[2:2 + STRIPS * BANDS] = bytes(int(c) for c in self.colours.reshape(-1))
        head[2 + STRIPS * BANDS:2 + STRIPS * BANDS + BANDS] = bytes(0x80 if c else 0 for c in self.changes)
        body = b''.join(self.line_bytes(y) for y in range(self.first, self.first + self.height))
        return bytes(head) + body + bytes(-len(body) % 128)


def decode(record):
    """What the Atari shows for a disk record: LINES x WIDTH x 3 (RGB), as Picture.rgb()."""
    first, height = record[0] - TOP, record[1]
    colours = np.array(list(record[2:2 + STRIPS * BANDS])).reshape(STRIPS, BANDS)
    bits = np.zeros((LINES, WIDTH), dtype=bool)
    cover = np.zeros((LINES, WIDTH // 2), dtype=bool)
    for i in range(height):
        line = record[128 + 16 * i:144 + 16 * i]
        row = np.unpackbits(np.frombuffer(line[:BYTES], dtype=np.uint8)).astype(bool)
        bits[first + i] = row[LEFT - 8 * BYTE0:LEFT - 8 * BYTE0 + WIDTH]
        for s in range(4):
            cover[first + i, s * CELLS:(s + 1) * CELLS] = np.unpackbits(np.uint8(line[BYTES + s])).astype(bool)
        cover[first + i, 4 * CELLS:] = [line[BYTES + 4] >> (c ^ 1) & 1 for c in range(CELLS)]
    unlit, lit = cell_colours(colours, cover)
    return PAL[np.where(bits, lit, unlit)].astype(np.uint8)


def load_sprite(path):
    """The sprite cropped and scaled to hi-res pixels (a source pixel is 4/3 wide)."""
    im = Image.open(path).convert('RGB')
    a = np.array(im)
    ys, xs = np.nonzero(a.sum(axis=2))
    im = im.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
    bw, bh = im.size
    s = min(1.0, LINES / bh, WIDTH / (bw * 4 / 3))
    w, h = min(WIDTH, round(bw * 4 / 3 * s)), min(LINES, round(bh * s))
    w -= w & 1
    return np.array(im.resize((w, h), Image.LANCZOS), dtype=float).clip(0, 255)


def convert_sprite(path):
    sprite = load_sprite(path)
    h, w = sprite.shape[:2]
    y0 = (LINES - h) // 2
    centre = (WIDTH - w) // 2 & ~1
    best = None
    for x0 in range(max(0, centre - 6), min(WIDTH - w, centre + 6) + 1, 2):     # the strips' best fit
        canvas = np.zeros((LINES, WIDTH, 3))
        canvas[y0:y0 + h, x0:x0 + w] = sprite
        error, colours, cover = choose(canvas)
        error += 0.002 * error * abs(x0 - centre)
        if best is None or error < best[0]:
            best = (error, canvas, colours, cover)
    _, canvas, colours, cover = best
    return Picture(diffuse(canvas, *cell_colours(colours, cover)), cover, colours)


def apple_bits(record):
    """An Apple picture (50 lines of 10 bytes) as the Atari shows it: 50 x 80 pixels."""
    bits = np.zeros((50, 80), dtype=bool)
    for y in range(50):
        for b in range(10):
            v = record[y * 10 + b]
            for i in range(7):
                bits[y, b * 8 + i] = v >> i & 1
            bits[y, b * 8 + 7] = v >> 6 & 1
    return bits


def convert_tinted(record, colour):
    """An Apple picture in one colour: every cell from a line's first lit pixel to its last."""
    bits = np.zeros((LINES, WIDTH), dtype=bool)
    bits[23 - TOP:73 - TOP] = apple_bits(record)
    cover = np.zeros((LINES, WIDTH // 2), dtype=bool)
    for y in range(LINES):
        xs = np.nonzero(bits[y])[0]
        if len(xs):
            cover[y, xs[0] // 2:xs[-1] // 2 + 1] = True
    colours = np.zeros((STRIPS, BANDS), dtype=int)
    for s in range(STRIPS):
        for b in range(BANDS):
            if cover[b * BAND:(b + 1) * BAND, s * CELLS:(s + 1) * CELLS].any():
                colours[s, b] = colour
    return Picture(bits, cover, colours)


def checksum(record):
    return sum(record[:500]) & 0xFFFF


def assign(scenario, mode='monster'):
    """(sprite name of each picture, picture of each monster); the chest and the gold follow."""
    names, index_of, of_monster = [], {}, []
    for unknown, name, pic in monsters(scenario):
        key = name if mode == 'monster' else (unknown, pic)
        if key not in index_of:
            index_of[key] = len(names)
            names.append(sprite_name(name))
        of_monster.append(index_of[key])
    return names, of_monster


def picture_set(scenario, mode='monster'):
    """(pictures, picture of each monster, chest index, gold index, chest sum, gold sum, names)."""
    names, of_monster = assign(scenario, mode)
    converted = {}
    pictures = []
    for name in names:
        if name not in converted:
            converted[name] = convert_sprite(sprite_path(name))
        pictures.append(converted[name])
    chest, gold = (scenario.record('ZSPCCHRS', n) for n in (CHEST, GOLD))
    pictures += [convert_tinted(chest, TINT[CHEST]), convert_tinted(gold, TINT[GOLD])]
    assert checksum(chest) != checksum(gold)
    return pictures, of_monster, len(names), len(names) + 1, checksum(chest), checksum(gold), names + ['chest', 'gold']


def cache_key(scenario, mode):
    h = hashlib.sha256(Path(__file__).read_bytes() + PALETTE.read_bytes() + mode.encode())
    h.update(scenario.data)
    for path in sorted(ART.glob('*.png')):
        h.update(path.name.encode() + path.read_bytes())
    return h.hexdigest()


def tables_include(of_monster, chest, gold, chest_sum, gold_sum, starts):
    """ca65 tables for src/picture.s; `starts` are sector offsets from PICS_SECTOR."""
    def rows(name, values):
        return [f'{name}:'] + ['        .byte ' + ', '.join(map(str, values[i:i + 24]))
                               for i in range(0, len(values), 24)]
    lines = ['; Generated by build.py (port/atari/pictures.py): the redrawn pictures.',
             f'MONSTERS = {len(of_monster)}', f'PIC_CHEST = {chest}', f'PIC_GOLD = {gold}',
             f'CHEST_SUM = {chest_sum}', f'GOLD_SUM = {gold_sum}']
    lines += rows('pic_of_monster', of_monster)
    lines += rows('pic_sec_lo', [f'<(PICS_SECTOR+{s})' for s in starts])
    lines += rows('pic_sec_hi', [f'>(PICS_SECTOR+{s})' for s in starts])
    return '\n'.join(lines) + '\n'


def sheet(pictures, names, path, columns=10):
    """A preview at the emulator's pixel shape (hi-res pixels a little narrower than tall)."""
    tw, th, pad = round(WIDTH * 2.75), LINES * 3, 6
    rows = -(-len(pictures) // columns)
    out = Image.new('RGB', (columns * (tw + pad) + pad, rows * (th + pad) + pad), (48, 48, 48))
    for i, p in enumerate(pictures):
        tile = Image.fromarray(p.rgb()).resize((tw, th), Image.NEAREST)
        out.paste(tile, (pad + (i % columns) * (tw + pad), pad + (i // columns) * (th + pad)))
    out.save(path)
    for i, name in enumerate(names):
        print(f'{i:3} {name}: {sum(pictures[i].changes)} interrupts')


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--scenario', default=PROJECT / 'appleII/images/wizardry_i/snafaru_restored_scenario.dsk')
    parser.add_argument('--fetch', action='store_true', help='download the sprites to art/pce/')
    parser.add_argument('--sheet', help='write a preview of every picture')
    parser.add_argument('--mode', default='monster', choices=['monster', 'class'])
    args = parser.parse_args()
    scenario = Scenario(args.scenario)
    if args.fetch:
        fetch(scenario)
    if args.sheet:
        pictures, *_, names = picture_set(scenario, args.mode)
        sheet(pictures, names, args.sheet)


if __name__ == '__main__':
    main()
