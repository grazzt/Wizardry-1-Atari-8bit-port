"""Two-disk build tests: real disk swaps through the game's own prompts.

    python3 port/atari/build.py --disk2 --test-images
    python3 -m unittest discover -s port/atari/tests -t port/atari

Disk 1 is the program disk (the runtime and the trimmed boot volume), disk 2
the scenario disk (the save disk). The emulator runs with fast disk access
off, so every SIO transfer takes its real time. The drive 1 image is hot-
swapped at the moments a disk is asked for: the game's own "PLACE ... IN
DRIVE 1, PRESS RETURN" prompts and FINDFILE loops are the player-facing
prompts and the verification, and the runtime's "CHANGE TO DISK 2" prompt is
the one at the chain into the game.

The title animation runs in real time on the Atari but instantly in pvm.
The tests synchronise RNG state at the options screen and key-poll counts
thereafter, allowing gameplay saves to match the reference byte for byte.
"""
import os
import re
import sys
import struct
import json
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / 'tools'))

from harness import LIBRARY                       # noqa: E402

DISK1 = HERE / 'build/test_disk1.atr'
DISK2 = HERE / 'build/test_disk2.atr'

CREATE_AND_SAVE = ['\r', '\r', 'E', 'T', 'ALICE\r', 'Y', '\r', '\r', 'A', 'A',
                   '+' * 10, '\x1b', 'A', 'Y', '\r', 'C', 'E', 'L']


def _norm(text):
    """Normalise the fields affected by the title-animation RNG offset."""
    text = re.sub(r'SER:\S*', 'SER:X', text)
    text = re.sub(r'POINTS\s+\d+', 'POINTS X', text)
    return text


def scenario_from_disk2(atr_bytes):
    """The scenario volume of a two-disk build's disk 2 (block order from
    sector 0) as a DOS-order .dsk, for PascalDisk."""
    from ucsd.disk import _DOS_ORDER, PascalDisk
    from build import volume_blocks
    body = atr_bytes[16:]
    read = volume_blocks(body, 0)
    image = bytearray(143360)
    for block in range(280):
        chunk = body[block * 512:block * 512 + 512] if read is None else read(block)
        track, index = divmod(block, 8)
        a, b = _DOS_ORDER[index]
        image[(track * 16 + a) * 256:(track * 16 + a + 1) * 256] = chunk[:256]
        image[(track * 16 + b) * 256:(track * 16 + b + 1) * 256] = chunk[256:]
    return PascalDisk(bytes(image), 'disk2')


@unittest.skipUnless(LIBRARY.exists() and DISK1.exists() and DISK2.exists(),
                     'build the two-disk test images: build.py --disk2 --test-images')
class Disk2Tests(unittest.TestCase):
    """The two-disk build, played with real (emulated) disk swaps."""

    disk1, disk2 = DISK1, DISK2

    def setUp(self):
        from lockstep import Lockstep
        self.run = Lockstep(atr=self.disk1, disk2=self.disk2, title=True, sio_patch=False)
        self.addCleanup(self.run.close)

    def assert_screen(self, ref, got):
        from lockstep import bitmap_diff, diff
        self.assertFalse(self.run.error, f'execution error\n{diff(ref, got)}')
        self.assertEqual(_norm(ref), _norm(got), diff(ref, got))
        self.assertEqual(self.run.graphics[0], self.run.graphics[1])
        if self.run.graphics[0]:
            self.assertEqual(bitmap_diff(self.run.vm, self.run.atari), [])

    def wait_for(self, text, limit=200000):
        for _ in range(limit // 30):
            self.run.atari.frame(30)
            if text in self.run.atari.text_memory():
                return
        self.fail(f'{text!r} never appeared')

    def to_options(self):
        """Through the title to the options screen, where lockstep resumes."""
        self.run.vm.send(' ')
        self.run.atari.type(' ')
        self.wait_for('VERSION 2.1')
        got = self.run.settle()
        self.assertEqual(_norm(self.run.vm.console.text()), _norm(got))
        # The animated title stirs the RNG in real time; synchronise at the
        # options screen so gameplay and saves can then match byte for byte.
        self.run.typed = self.run.vm.console.keys_read
        for i, addr in enumerate((0x47A, 0x4FA, 0x57A, 0x5FB)):
            self.run.atari.memory[0xC0 + i] = self.run.vm.mem[addr]

    def through_prompt(self):
        """The chain prompt: swap in disk 2, press the key, back in lockstep."""
        self.assertTrue(self.run.at_prompt)
        self.assertIn('CHANGE TO DISK 2', self.run.atari.text_memory())
        self.run.swap_disk()
        self.run.atari.type('\r')
        self.run.settle()
        self.assertFalse(self.run.at_prompt)
        self.assertFalse(self.run.error)

    def disk2_with_scenario(self, scenario_disk):
        entry = scenario_disk.entry('SCENARIO.DATA')
        data = scenario_disk.read('SCENARIO.DATA')
        body = bytearray(self.disk2.read_bytes())
        from build import volume_blocks
        read = volume_blocks(body[16:], 0)
        if read is None:
            at = 16 + entry.first_block * 512
            body[at:at + len(data)] = data
        else:
            layout = self.run.layout
            for index in range(len(data) // 512):
                block = entry.first_block + index
                chunk = data[index * 512:(index + 1) * 512]
                if chunk == read(block):
                    continue
                map_at = 16 + (layout['MAP_START'] - 1) * 128 + layout['MAP_DATA'] + index * 3
                sector, ctl = struct.unpack_from('<HB', body, map_at)
                self.assertTrue(ctl & 0x80, 'changed cache must be writable')
                at = 16 + (sector - 1) * 128 + (ctl & 0x7F)
                body[at:at + 512] = chunk
        path = Path(tempfile.gettempdir()) / f'disk2_out_{os.getpid()}.atr'
        path.write_bytes(bytes(body))
        return path

    def test_start_swap_and_castle(self):
        self.to_options()
        ref, got = self.run.step('S')
        self.through_prompt()
        ref, got = self.run.step('\r')
        self.assert_screen(ref, got)
        self.assertIn('MASTER/DUPLICATE IN DRV 1', got)
        ref, got = self.run.step('\r')
        self.assert_screen(ref, got)
        self.assertIn('! CASTLE', got)

    def test_wrong_disk_loops(self):
        self.to_options()
        ref, got = self.run.step('S')
        self.assertTrue(self.run.at_prompt)
        self.run.atari.type('\r')
        got = self.run.settle()
        self.assertIn('WRONG DISK', got)
        self.assertTrue(self.run.at_prompt)
        self.assertFalse(self.run.error)
        self.run.swap_disk()
        self.run.atari.type('\r')
        self.run.settle()
        self.assertFalse(self.run.at_prompt)
        self.assertFalse(self.run.error)
        ref, got = self.run.step('\r')
        self.assert_screen(ref, got)

    def test_recover_across_real_swap(self):
        from pvm.tests.test_pvm import out_scenario, title_machine
        out = out_scenario()
        modified = self.disk2_with_scenario(out)
        self.run.vm = title_machine(scenario=out, seed=1)
        self.run.vm.send('')
        self.run.typed = 0
        self.run.disk2 = modified
        self.to_options()
        ref, got = self.run.step('U')
        self.assert_screen(ref, got)
        ref, got = self.run.step('R')
        self.assert_screen(ref, got)
        ref, got = self.run.step('\r')
        self.assert_screen(ref, got)
        self.wait_for('PLACE SCENARIO IN DRIVE 1')
        self.run.swap_disk()
        ref, got = self.run.step('\r')
        self.assert_screen(ref, got)
        self.assertIn('ALICE SAVED', got)
        ref, got = self.run.step('\r')
        self.assert_screen(ref, got)
        ref, got = self.run.step('L')
        self.wait_for('PLACE BOOT DISK IN DRIVE 1')
        self.run.swap_disk(self.disk1)
        self.run.atari.type('\r')
        self.run.settle()
        self.assertEqual(_norm(self.run.vm.console.text()), _norm(self.run.atari.text_memory()))
        self.assertIn('S)TART GAME', self.run.atari.text_memory())
        ref, got = self.run.step('S')
        self.through_prompt()
        ref, got = self.run.step('\r')
        self.assert_screen(ref, got)
        ref, got = self.run.step('\r')
        self.assert_screen(ref, got)
        self.assertIn('! CASTLE', got)

    def test_create_save_on_disk2(self):
        self.to_options()
        ref, got = self.run.step('S')
        self.through_prompt()
        for keys in CREATE_AND_SAVE:
            ref, got = self.run.step(keys)
            self.assertFalse(self.run.error, f'execution error after {keys!r}')
        self.assertIn('PRESS [RETURN] FOR MORE WIZARDRY', self.run.atari.text_memory())
        from ucsd.disk import PascalDisk
        host = PascalDisk(bytes(self.run.vm.units[4].image), 'host')
        atari = scenario_from_disk2(self.run.disk2.read_bytes())
        host_data = host.read('SCENARIO.DATA')
        atari_data = atari.read('SCENARIO.DATA')
        self.assertEqual(len(host_data), len(atari_data))
        self.assertIn(b'ALICE', atari_data)
        self.assertEqual(atari_data, host_data)


@unittest.skipUnless(LIBRARY.exists() and (HERE / 'build/test_pce_disk1.atr').exists(),
                     'build.py --disk2 --pictures monster --testmode --out test_pce.atr')
class PceDisk2Tests(Disk2Tests):
    disk1 = HERE / 'build/test_pce_disk1.atr'
    disk2 = HERE / 'build/test_pce_disk2.atr'

    def play(self, script):
        from lockstep import bitmap_diff, diff, picture_check, redrawn_picture
        scenario = HERE.parents[1] / 'appleII/images/wizardry_i/wizardry_i_scenario.dsk'
        self.run.close()
        from lockstep import Lockstep
        self.run = Lockstep(atr=HERE / 'build/played_pce_disk1.atr',
                            disk2=HERE / 'build/played_pce_disk2.atr',
                            scenario=scenario, title=False, sio_patch=False)
        self.addCleanup(self.run.close)
        self.run.settle()
        self.through_prompt()
        music_expected = [1]
        heard, jingles = set(), set()
        if self.run.layout.get('MUSIC'):
            import music
            original_call = self.run.vm.call
            def track_music(segment, procedure):
                caller_segment = self.run.vm.seg.number
                caller_procedure = self.run.vm.frame.proc.number
                for seg, proc, from_seg, from_proc, song in music.CUES:
                    if (seg, proc) == (segment, procedure) and (not from_seg or
                            (from_seg, from_proc) == (caller_segment, caller_procedure)):
                        if song < 15:
                            music_expected[0] = song
                            heard.add(song)
                        else:
                            jingles.add(song)
                return original_call(segment, procedure)
            self.run.vm.call = track_music
            self.assertEqual(self.run.atari.peek(self.run.labels['ml_player_ready']), 1)
            self.assertEqual(self.run.atari.peek(self.run.labels['ml_jingles']), 15)
        pictures = 0
        shown = False
        keys = json.loads((HERE / 'tests' / script).read_text())['keys']
        for i, key in enumerate(keys):
            ref, got = self.run.step(key)
            self.assertFalse(self.run.error, f'execution error at {i} {key!r}')
            self.assertEqual(ref, got, f'key {i} {key!r}:\n{diff(ref, got)}')
            self.assertEqual(*self.run.graphics)
            if self.run.layout.get('MUSIC'):
                self.assertEqual(self.run.atari.peek(self.run.labels['cur_song']), music_expected[0],
                                 f'music cue at key {i}')
                self.assertEqual(self.run.atari.peek(self.run.labels['ml_failed']), 0,
                                 f'music load failed at key {i}')
            if self.run.graphics[0]:
                self.assertEqual(bitmap_diff(self.run.vm, self.run.atari), [], f'bitmap at {i}')
            was, shown = shown, self.run.graphics[0] and redrawn_picture(self.run.atari)
            if shown and not was:
                self.run.atari.frame(2)
                self.assertIsNone(picture_check(self.run, scenario), f'picture at {i}')
                pictures += 1
        self.assertGreater(pictures, 0)
        if self.run.layout.get('MUSIC'):
            places = {2, 3, 5, 7, 8, 9, 10}
            places.add(4 if script == 'adventure_keys.json' else 6)
            self.assertTrue(places <= heard, heard)
            self.assertTrue({15, 16} <= jingles, jingles)
        self.assertIn('PRESS [RETURN] FOR MORE WIZARDRY', got)
        from ucsd.disk import PascalDisk
        host = PascalDisk(bytes(self.run.vm.units[4].image), 'host')
        actual = scenario_from_disk2(self.run.disk2.read_bytes())
        self.assertEqual(actual.read('SCENARIO.DATA'), host.read('SCENARIO.DATA'))

    def test_adventure_and_save(self):
        self.play('adventure_keys.json')

    def test_spells_and_inn(self):
        self.play('adventure2_keys.json')


if __name__ == '__main__':
    unittest.main()
