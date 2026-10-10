"""Atari runtime vs the host p-machine, in lockstep.

    python3 port/atari/build.py --test-images
    python3 -m unittest discover -s port/atari/tests -t port/atari

After every key both machines must show the same text screen, be in the same
display mode, and (in graphics mode) have the same bitmap once the Apple
hi-res page is mapped to the Atari layout. Skipped if libatari800 or the
test-mode build is missing.
"""
from pathlib import Path
import random
import sys
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / 'tools'))

from harness import LIBRARY                       # noqa: E402

BUILD = HERE / 'build/test.atr'
CREATE_AND_SAVE = ['\r', '\r', 'E', 'T', 'ALICE\r', 'Y', '\r', '\r', 'A', 'A', '+' * 10, '\x1b',
                   'A', 'Y', '\r', 'C', 'E', 'L']
# "Press RETURN for more Wizardry", restart, then add ALICE and enter the maze.
INTO_MAZE = ['\r', '\r', '\r', 'G', 'A', 'ALICE\r', '\r', '\r', 'E', 'M', 'L']


def atr_to_dsk(atr_bytes):
    """The ATR holds the scenario volume's Pascal blocks in order (after the
    boot sectors, tables and boot volume); rebuild a DOS-order 140K image."""
    import json
    from ucsd.disk import _DOS_ORDER
    volstart = json.loads((HERE / 'build/layout.json').read_text())['SCENVOL']
    data = atr_bytes[16 + (volstart - 1) * 128:]
    image = bytearray(143360)
    for block in range(280):
        chunk = data[block * 512:(block + 1) * 512]
        track, index = divmod(block, 8)
        a, b = _DOS_ORDER[index]
        image[(track * 16 + a) * 256:(track * 16 + a + 1) * 256] = chunk[:256]
        image[(track * 16 + b) * 256:(track * 16 + b + 1) * 256] = chunk[256:]
    return bytes(image)


def with_scenario_data(atr_bytes, disk):
    """An ATR whose scenario volume holds `disk`'s SCENARIO.DATA (the rest of
    the volume, with the patched WIZARDRY.CODE, is kept)."""
    import json
    volstart = json.loads((HERE / 'build/layout.json').read_text())['SCENVOL']
    entry = disk.entry('SCENARIO.DATA')
    data = bytearray(atr_bytes)
    for block in range(entry.first_block, entry.next_block):
        at = 16 + (volstart - 1) * 128 + block * 512
        data[at:at + 512] = disk.block(block)
    return bytes(data)


def redrawn_pictures():
    """True if the test images were built with the redrawn pictures (pictures.py)."""
    import json
    return bool(json.loads((HERE / 'build/layout.json').read_text()).get('SPRITES'))


@unittest.skipUnless(LIBRARY.exists() and BUILD.exists(), 'needs libatari800 and build.py --test-images')
class LockstepTests(unittest.TestCase):
    def setUp(self):
        from lockstep import Lockstep
        self.run = Lockstep()
        self.addCleanup(self.run.close)

    def press(self, keys):
        from lockstep import bitmap_diff, diff
        ref, got = self.run.step(keys)
        self.assertFalse(self.run.error, f'execution error after {keys!r}')
        self.assertEqual(ref, got, f'text after {keys!r}:\n{diff(ref, got)}')
        host_gfx, atari_gfx = self.run.graphics
        self.assertEqual(host_gfx, atari_gfx, f'display mode after {keys!r}')
        if host_gfx:
            rows = bitmap_diff(self.run.vm, self.run.atari)
            self.assertEqual(rows, [], f'bitmap rows differ after {keys!r}')

    def test_character_creation_and_save(self):
        from ucsd.disk import PascalDisk
        for keys in CREATE_AND_SAVE:
            self.press(keys)
        atari = PascalDisk(atr_to_dsk(self.run.atr.read_bytes()), 'atari')
        host = PascalDisk(bytes(self.run.vm.units[4].image), 'pvm')
        self.assertEqual(atari.read('SCENARIO.DATA'), host.read('SCENARIO.DATA'))

    def test_maze_and_battle(self):
        for keys in CREATE_AND_SAVE + INTO_MAZE:
            self.press(keys)
        self.assertSong(8, 'in the maze')
        walk = random.Random(3)
        for _ in range(200):
            self.press(walk.choice('FFFFLR'))
            self.press('N')                               # answer any stairs prompt
            if 'CUTIL' in self.run.vm.loaded_names():
                break
        else:
            self.fail('no encounter')
        self.assertSong(10, 'combat')                     # the NES fight theme
        for _ in range(40):                               # fight group 1 until it ends
            if 'CUTIL' not in self.run.vm.loaded_names():
                break
            for keys in ('F', '1', '\r'):
                self.press(keys)
        self.assertNotIn('CUTIL', self.run.vm.loaded_names())
        self.assertSong(12, 'ALICE fell: the cemetery')   # the NES "Exterminated"

    def assertSong(self, song, where):
        """The theme loaded for the place (NSF numbering), if the build has music."""
        labels = {line.split()[2].lstrip('.'): int(line.split()[1], 16)
                  for line in (HERE / 'build/labels.txt').read_text().splitlines()}
        if 'cur_song' in labels:
            self.assertEqual(self.run.atari.peek(labels['cur_song']), song, where)


@unittest.skipUnless(LIBRARY.exists() and (HERE / 'build/played.atr').exists(),
                     'needs libatari800 and build.py --test-images')
class AdventureTests(unittest.TestCase):
    """A full party from the played scenario disk: town, camp spell, maze,
    a won battle, the way back, and a save. Keys were found on pvm."""

    def play(self, script_name):
        import json
        from lockstep import Lockstep, bitmap_diff, diff, picture_check, redrawn_picture
        from ucsd.disk import PascalDisk
        script = json.loads((Path(__file__).parent / script_name).read_text())
        scenario = HERE.parents[1] / script['scenario']
        run = Lockstep(atr=HERE / 'build/played.atr', scenario=scenario)
        self.addCleanup(run.close)
        pictures, shown = 0, False
        for i, keys in enumerate(script['keys']):
            ref, got = run.step(keys)
            self.assertFalse(run.error, f'execution error at key {i} {keys!r}')
            self.assertEqual(ref, got, f'text at key {i} {keys!r}:\n{diff(ref, got)}')
            self.assertEqual(*run.graphics, f'display mode at key {i}')
            if run.graphics[0]:
                self.assertEqual(bitmap_diff(run.vm, run.atari), [], f'bitmap at key {i} {keys!r}')
            was, shown = shown, run.graphics[0] and redrawn_picture(run.atari)
            if shown and not was:           # a redrawn picture appeared: the right one, exactly?
                run.atari.frame(2)
                self.assertIsNone(picture_check(run, scenario), f'at key {i} {keys!r}')
                pictures += 1
        self.assertIn('PRESS [RETURN] FOR MORE WIZARDRY', ref)
        if redrawn_pictures():
            self.assertGreater(pictures, 0, 'no picture was shown')
        atari = PascalDisk(atr_to_dsk(run.atr.read_bytes()), 'atari')
        host = PascalDisk(bytes(run.vm.units[4].image), 'pvm')
        self.assertEqual(atari.read('SCENARIO.DATA'), host.read('SCENARIO.DATA'))
        self.assertNotEqual(host.read('SCENARIO.DATA'), PascalDisk.open(scenario).read('SCENARIO.DATA'))

    def test_adventure_and_save(self):
        self.play('adventure_keys.json')

    def test_spells_and_inn(self):
        """3,005 keys; about a minute (the inn heals in real time on the Atari)."""
        self.play('adventure2_keys.json')

@unittest.skipUnless(LIBRARY.exists() and (HERE / 'build/title.atr').exists(),
                     'needs libatari800 and build.py --test-images')
class TitleTests(unittest.TestCase):
    """SYSTEM.STARTUP: title animation, options screen, chain to the game.
    The animation runs in real time, so screens are compared with pvm only
    where the program waits for a key."""

    def test_title_options_and_chain(self):
        import shutil
        import tempfile
        from harness import Atari
        from pvm.tests.test_pvm import title_machine
        work = tempfile.TemporaryDirectory()
        self.addCleanup(work.cleanup)
        atr = Path(work.name) / 'title.atr'
        shutil.copyfile(HERE / 'build/title.atr', atr)
        atari = Atari(atr)
        atari.frame(600)
        self.assertTrue(atari.peek(0x00B4), 'the title should be in graphics mode')
        self.assertTrue(any(atari.memory[0x2000:0x3E10]), 'the title should draw on the bitmap')
        vm = title_machine()
        for keys, settle in ((' ', 400), ('S', 600), ('\r', 300), ('\r', 600)):
            atari.type(keys)
            atari.frame(settle)
            vm.send(keys)
            self.assertNotEqual(atari.peek(0x0585), 0xEE, f'execution error after {keys!r}')
            self.assertEqual(atari.text_memory(), vm.console.text(), f'after {keys!r}')
        self.assertIn('! CASTLE', vm.console.text())

    @unittest.skipUnless((HERE.parents[1] / 'nes/snafaru/wiz1.nsf').exists(), 'needs the NES music (nes/)')
    def test_title_music(self):
        """The NES title theme plays over the title; the castle theme follows in the game."""
        import shutil
        import tempfile
        from harness import Atari
        work = tempfile.TemporaryDirectory()
        self.addCleanup(work.cleanup)
        atr = Path(work.name) / 'title.atr'
        shutil.copyfile(HERE / 'build/title.atr', atr)
        labels = {line.split()[2].lstrip('.'): int(line.split()[1], 16)
                  for line in (HERE / 'build/labels.txt').read_text().splitlines()}
        # (libatari800 is loaded once per process, so its sound output depends
        # on the first test; the player's state is checked instead. The VBI
        # player clears mus_rew when it starts a song.)
        atari = Atari(atr)
        atari.frame(600)
        self.assertEqual((atari.peek(labels['mus_main']), atari.peek(labels['mus_rew'])), (1, 0),
                         'the title song should be playing')
        for keys, settle in ((' ', 400), ('S', 600), ('\r', 300), ('\r', 600)):
            atari.type(keys)
            atari.frame(settle)
        self.assertEqual(atari.peek(labels['cur_song']), 2, 'the castle theme')
        self.assertEqual((atari.peek(labels['mus_main']), atari.peek(labels['mus_rew'])), (1, 0),
                         'the castle theme should be playing')
        self.assertIn('CASTLE', atari.text_memory())

    def test_recover_out_character(self):
        """U)TILITIES R)ECOVER: the utilities' disk swaps happen on the one disk."""
        import tempfile
        from harness import Atari
        from ucsd.disk import PascalDisk
        from pvm.tests.test_pvm import RECOVER, out_scenario, title_machine
        out = out_scenario()
        work = tempfile.TemporaryDirectory()
        self.addCleanup(work.cleanup)
        atr = Path(work.name) / 'title.atr'
        atr.write_bytes(with_scenario_data((HERE / 'build/title.atr').read_bytes(), out))
        atari = Atari(atr)
        atari.frame(600)
        vm = title_machine(scenario=out)
        for i, keys in enumerate(RECOVER + ['\r', 'L', 'S', '\r', '\r']):
            atari.type(keys)
            atari.frame(600)
            vm.send(keys)
            self.assertNotEqual(atari.peek(0x0585), 0xEE, f'execution error after {keys!r}')
            self.assertEqual(atari.text_memory(), vm.console.text(), f'after {keys!r}')
            if i == len(RECOVER) - 1:
                self.assertIn('ALICE SAVED', vm.console.text())
        self.assertIn('! CASTLE', vm.console.text())
        del atari
        disk = PascalDisk(atr_to_dsk(atr.read_bytes()), 'atari')
        host = PascalDisk(bytes(vm.units[4].image), 'pvm')
        self.assertEqual(disk.read('SCENARIO.DATA'), host.read('SCENARIO.DATA'))
        self.assertNotEqual(host.read('SCENARIO.DATA'), out.read('SCENARIO.DATA'))


if __name__ == '__main__':
    unittest.main()
