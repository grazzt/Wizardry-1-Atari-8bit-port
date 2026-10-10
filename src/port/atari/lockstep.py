"""Run the same key script on the Atari runtime and on pvm; compare screens.

The Atari runs in test mode: each key wait stirs the game's RNG exactly as
many times as pvm did for that key, so random outcomes match too.
"""
import difflib
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / 'tools'))

from harness import Atari                         # noqa: E402
from pvm.tests.test_pvm import machine            # noqa: E402

TESTMODE, TESTPOLLS, WAITING, ERROR_MARK, GFX_MODE = 0x05F0, 0x05F2, 0x05F4, 0x0585, 0x00B4


class Lockstep:
    def __init__(self, atr=HERE / 'build/test.atr', seed=1, scenario=None, sound=False):
        """`scenario` is the Apple scenario image pvm uses; it must be the one
        the ATR was built from (default: the clean-roster disk)."""
        # The emulator writes saves back into the image, so work on a copy.
        self.workdir = tempfile.TemporaryDirectory()
        self.atr = Path(self.workdir.name) / 'wizardry.atr'
        shutil.copyfile(atr, self.atr)
        self.atari = Atari(self.atr, sound=sound)
        self.atari.frame(60)
        if not self.atari.peek(TESTMODE):
            raise RuntimeError('build the test images with: build.py --test-images')
        self.vm = machine(scenario, seed=seed) if scenario else machine(seed=seed)
        self.vm.send('')
        self.typed = 0

    def settle(self, limit=200000):
        """Run frames until the Atari waits for a key (or reports an error).
        Some screens take a while: resting at the inn heals week by week with
        a delay loop, which pvm runs instantly but the Atari runs in real time."""
        for _ in range(limit // 10):
            self.atari.frame(10)
            if self.atari.peek(WAITING) or self.error:
                self.atari.frame(2)
                break
        return self.atari.text_memory()

    def step(self, keys):
        """Type keys on both machines; return (pvm screen, Atari screen)."""
        self.vm.send(keys)
        for ch in keys:
            self.settle()               # one key at a time, as a person types
            polls = self.vm.poll_log.get(self.typed, 0)
            self.atari.memory[TESTPOLLS] = polls & 0xFF
            self.atari.memory[TESTPOLLS + 1] = polls >> 8
            self.atari.type(ch)
            self.typed += 1
        return self.vm.console.text(), self.settle()

    def close(self):
        self.workdir.cleanup()

    @property
    def graphics(self):
        """(pvm, Atari) graphics-mode flags."""
        return self.vm.display['graphics'], bool(self.atari.peek(GFX_MODE))

    @property
    def error(self):
        return self.atari.peek(ERROR_MARK) == 0xEE


def expand7(byte):
    """Apple hi-res byte -> Atari mode F byte (see src/natives.s)."""
    out = 0
    for bit in range(7):
        if byte >> bit & 1:
            out |= 0x80 >> bit
    return out | (1 if byte & 0x40 else 0)


def apple_bitmap(vm):
    """pvm's hi-res page converted to the Atari layout: 192 rows of 40 bytes."""
    mem = vm.mem
    rows = []
    for y in range(192):
        base = 0x2000 + (y & 7) * 0x400 + ((y >> 3) & 7) * 0x80 + (y >> 6) * 0x28
        rows.append(bytes(expand7(mem[base + c]) for c in range(40)))
    return rows


def atari_bitmap(atari):
    rows = []
    for y in range(192):
        base = 0x2000 + 40 * y + (16 if y >= 102 else 0)
        rows.append(bytes(atari.memory[base:base + 40]))
    return rows


def labels():
    """The last build's labels: name -> address."""
    return {line.split()[2].lstrip('.'): int(line.split()[1], 16)
            for line in (HERE / 'build/labels.txt').read_text().splitlines()}


def redrawn_picture(atari):
    """True while the Atari shows one of its own pictures (pictures.py) in the box."""
    import json
    if not json.loads((HERE / 'build/layout.json').read_text()).get('SPRITES'):
        return False
    return bool(atari.peek(labels()['pic_on']))


def picture_check(run, scenario):
    """While the Atari shows a redrawn picture: None if it is the right one, shown
    exactly as pictures.py predicts from the disk record; else what is wrong.
    Which picture is right comes from pvm: the Apple picture on its hi-res page
    (the chest and the gold) or its ENEMYINX (global 19: group 1's monster)."""
    import json
    import numpy as np
    import pictures
    from wizardry_scenario import Scenario
    layout = json.loads((HERE / 'build/layout.json').read_text())
    data = Scenario(scenario)
    names, of_monster = pictures.assign(data, layout['PICTURES'])
    mem = run.vm.mem
    shown = bytes(mem[0x2001 + (y & 7) * 0x400 + ((y >> 3) & 7) * 0x80 + (y >> 6) * 0x28 + c]
                  for y in range(23, 73) for c in range(10))
    apple = [n for n in range(20) if data.record('ZSPCCHRS', n)[:500] == shown]
    if not apple:
        return 'pvm shows no Apple picture'
    if 'COMBAT' in run.vm.loaded_names():
        index = of_monster[run.vm.load(run.vm.base.addr(19))]
    elif apple[0] in (pictures.CHEST, pictures.GOLD):
        index = len(names) + apple[0] - pictures.CHEST
    else:
        return f'Apple picture {apple[0]} outside a fight'
    at = 16 + (layout['PICS_SECTOR'] - 1 + layout['PICTURE_STARTS'][index]) * 128
    atr = run.atr.read_bytes()
    want = pictures.decode(atr[at:at + 128 + 16 * pictures.LINES])
    palette = np.array([list(c) for c in run.atari.palette()], dtype=np.uint8)
    screen = palette[np.frombuffer(run.atari.screen(), dtype=np.uint8).reshape(240, 384)]
    got = screen[24 + pictures.TOP:24 + pictures.TOP + pictures.LINES,
                 32 + pictures.LEFT:32 + pictures.LEFT + pictures.WIDTH]
    wrong = int((got != want).any(axis=2).sum())
    return f'picture {index} ({(names + ["chest", "gold"])[index]}): {wrong} pixels differ' if wrong else None


def bitmap_diff(vm, atari):
    """Rows where the two bitmaps differ. The picture box (rows 5-83, bytes 1-11)
    is left out while the Atari shows a redrawn picture there."""
    rows = list(zip(apple_bitmap(vm), atari_bitmap(atari)))
    if redrawn_picture(atari):
        rows = [(a[:1] + a[12:], b[:1] + b[12:]) if 5 <= y <= 83 else (a, b) for y, (a, b) in enumerate(rows)]
    return [y for y, (a, b) in enumerate(rows) if a != b]


def diff(a, b):
    return '\n'.join(difflib.unified_diff(a.splitlines(), (b or '').splitlines(), 'pvm', 'atari', lineterm=''))


if __name__ == '__main__':
    steps = ['\r', '\r', 'E', 'T', 'ALICE\r', 'Y', '\r', '\r', 'A', 'A', '+' * 10, '\x1b', 'A', 'Y',
             '\r', 'C', 'E', 'L']
    run = Lockstep()
    for keys in steps:
        ref, got = run.step(keys)
        print(repr(keys).ljust(14), 'match' if ref == got else 'DIFFERENT', 'ERROR' if run.error else '')
        if ref != got or run.error:
            print(diff(ref, got))
            sys.exit(1)
    print('all steps match')
