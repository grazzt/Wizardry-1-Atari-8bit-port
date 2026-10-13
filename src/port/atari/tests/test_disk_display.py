"""Watch intermediate Atari800 frames, including real SIO and decompression."""
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from harness import LIBRARY
from tests import test_party as party_support
MANIFEST = party_support.MANIFEST


@unittest.skipUnless(LIBRARY.exists() and MANIFEST.exists(), 'build the test_party disks')
class DiskDisplayTests(unittest.TestCase):
    def setUp(self):
        helper = party_support.AtariPartyTests()
        self.run = helper.formed_run()
        self.addCleanup(helper.doCleanups)
        self.atari = self.run.atari
        self.atari.frame(3)

    def test_party_rows_stay_visible_through_tavern_music_load(self):
        a = self.atari
        def pixels():
            screen = a.screen()
            return b''.join(screen[y * 384 + 32:y * 384 + 352] for y in range(64, 112))
        expected = pixels()
        roster = bytes(a.memory[0xBC00 + 5 * 40:0xBC00 + 11 * 40])
        checked, corrupt = [], []
        def watch():
            if bytes(a.memory[0xBC00 + 5 * 40:0xBC00 + 11 * 40]) == roster:
                checked.append(a.frames)
                if pixels() != expected:
                    corrupt.append(a.frames)
        a.on_frame = watch
        try:
            reference, actual = self.run.step('G')
        finally:
            a.on_frame = None
        self.assertEqual(reference, actual)
        self.assertGreater(len(checked), 20)
        self.assertEqual(corrupt, [], 'intermediate frames must retain the text font')

    def test_party_rows_stay_visible_through_maze_code_and_data_loads(self):
        a = self.atari
        def pixels():
            screen = a.screen()
            return b''.join(screen[y * 384 + 32:y * 384 + 352] for y in range(64, 112))
        expected = pixels()
        roster = bytes(a.memory[0xBC00 + 5 * 40:0xBC00 + 11 * 40])
        checked, corrupt = [], []
        def watch():
            if not a.peek(0xB4) and bytes(a.memory[0xBC00 + 5 * 40:0xBC00 + 11 * 40]) == roster:
                checked.append(a.frames)
                if pixels() != expected:
                    corrupt.append(a.frames)
        a.on_frame = watch
        try:
            for key in 'EML':
                reference, actual = self.run.step(key)
                self.assertEqual(reference, actual)
                self.assertFalse(self.run.error)
        finally:
            a.on_frame = None
        self.assertTrue(self.run.graphics[1])
        self.assertGreater(len(checked), 20)
        self.assertEqual(corrupt, [], 'code and data loads must retain the text font')
