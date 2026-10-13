"""Native music loading/player fidelity for the compressed two-disk runtime."""
import json
import pickle
import struct
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from tests import test_compression as support
import music
import twodisk_music


def register_frames(image, base):
    """Read the original player tables independently of the 6502 player."""
    frames = []
    for frame in range(image[0] * music.B * music.K):
        registers = [0] * 8
        for stream in range(6):
            d = image[2 + stream * 45:2 + (stream + 1) * 45]
            def pointer(offset):
                return struct.unpack_from('<H', d, offset)[0] - base
            pattern = image[pointer(1) + frame // 48]
            block = image[pointer(3 + 2 * ((frame // 6) % 8)) + pattern]
            for register in range(d[0]):
                slot = 19 + register * 13
                registers[d[slot]] = image[pointer(slot + 1 + 2 * (frame % 6)) + block]
        frames.append(bytes(registers))
    return frames


@unittest.skipUnless(support.MANIFEST.exists(), 'build the music-enabled test_pce disks')
class CompressedMusicTests(unittest.TestCase):
    def setUp(self):
        self.runtime = support.AssembledCompressionTests()
        self.runtime.setUp()
        self.mem = self.runtime.mem
        self.labels = self.runtime.labels
        if not self.runtime.layout.get('MUSIC'):
            self.skipTest('test_pce disks were built without music')
        _, images = pickle.loads((HERE / 'build/music.cache').read_bytes())
        self.images = twodisk_music.relocate_images(images)
        self.records = twodisk_music.records(self.images)

    def word(self, address, value):
        self.runtime.word(address, value)

    def frame(self):
        self.runtime.call('music_play')
        return bytes(self.mem[0xD200:0xD208])

    def load(self, song):
        self.runtime.cpu.x = song
        self.mem[0xAD] = 0x55
        self.runtime.call('music_load_cmp')
        self.assertEqual(self.mem[0xAD], 0x55, 'music must preserve game IORESULT')
        self.assertEqual(self.runtime.cpu.c, 1)

    def theme(self, song):
        self.load(song)
        self.mem[self.labels['mus_main']] = 1
        self.mem[self.labels['mus_rew']] = 1
        self.mem[self.labels['mus_jreq']] = 0
        self.mem[self.labels['mus_jing']] = 0

    def test_all_music_images_exact_and_vectors_preserved(self):
        self.mem[0xFFFA:] = b'VECTOR'
        for song, address, image in self.records:
            with self.subTest(song=song):
                self.mem[address - 1] = 0xA5
                self.mem[address + len(image)] = 0x5A
                self.load(song)
                self.assertEqual(self.mem[address:address + len(image)], image)
                self.assertEqual(self.mem[address - 1], 0xA5)
                self.assertEqual(self.mem[address + len(image)], 0x5A)
                self.assertEqual(self.mem[0xFFFA:], b'VECTOR')

    def test_every_theme_frame_loop_and_stop(self):
        for song, address, image in self.records:
            if song >= 15:
                continue
            with self.subTest(song=song):
                expected = register_frames(image, address)
                self.theme(song)
                for index, registers in enumerate(expected):
                    self.assertEqual(self.frame(), registers, f'song {song}, frame {index}')
                if image[1] == 255:
                    self.assertEqual(self.mem[self.labels['mus_main']], 0)
                    self.assertEqual(self.frame(), bytes(8))
                else:
                    loop = image[1] * 48
                    self.assertEqual(self.mem[self.labels['mus_p']], image[1])
                    for registers in expected[loop:loop + 96]:
                        self.assertEqual(self.frame(), registers)

    def test_every_jingle_and_theme_resume(self):
        castle = next((image for song, _, image in self.records if song == 2))
        first = register_frames(castle, twodisk_music.SLOT)[0]
        for song, address, image in self.records:
            if song < 15:
                continue
            with self.subTest(song=song):
                self.theme(2)
                self.frame()
                self.load(song)
                self.word(self.labels['mus_jaddr'], address)
                self.mem[self.labels['mus_jreq']] = 1
                for index, expected in enumerate(register_frames(image, address)):
                    self.assertEqual(self.frame(), expected, f'jingle {song}, frame {index}')
                self.assertEqual(self.mem[self.labels['mus_jing']], 0)
                self.assertEqual(self.frame(), first)
                self.assertEqual(self.mem[self.labels['mus_main']], 1)

    def test_music_load_failure_preserves_game_ioresult(self):
        def failed(cpu):
            cpu.n = 1
        self.runtime.cpu.traps[0xE459] = failed
        self.runtime.cpu.x = 2
        self.mem[0xAD] = 7
        self.runtime.call('music_load_cmp')
        self.assertEqual(self.mem[0xAD], 7)
        self.assertEqual(self.runtime.cpu.c, 0)

    def test_failed_jingles_are_not_requested(self):
        self.mem[self.labels['ml_player_ready']] = 1
        self.mem[self.labels['ml_jingles']] = 0
        self.runtime.cpu.a = 15
        self.runtime.call('music_song')
        self.assertEqual(self.mem[self.labels['mus_jreq']], 0)

    def test_failed_theme_can_retry(self):
        self.mem[self.labels['ml_player_ready']] = 1
        def failed(cpu):
            cpu.n = 1
        self.runtime.cpu.traps[0xE459] = failed
        self.runtime.cpu.a = 2
        self.runtime.call('music_song')
        self.assertEqual(self.mem[self.labels['cur_song']], 0)
        self.assertEqual(self.mem[self.labels['mus_main']], 0)
        self.runtime.cpu.traps[0xE459] = self.runtime.sio
        self.runtime.cpu.a = 2
        self.runtime.call('music_song')
        self.assertEqual(self.mem[self.labels['cur_song']], 2)
        self.assertEqual(self.mem[self.labels['mus_main']], 1)

    def test_player_does_not_touch_decoder_scratch(self):
        self.theme(2)
        self.mem[0xF4:0x100] = bytes(range(12))
        self.frame()
        self.assertEqual(self.mem[0xF4:0x100], bytes(range(12)))
