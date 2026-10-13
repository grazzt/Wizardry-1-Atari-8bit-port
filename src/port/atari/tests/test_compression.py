"""Lossless packing, actual assembled decoder, and writable scenario caches."""
import json
import random
import struct
import sys
import unittest
import tempfile
from unittest.mock import patch
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / 'tools'))
import build
import compress
import zx02
from ucsd.disk import PascalDisk
from ucsd.codefile import CodeFile
from pvm.cpu6502 import CPU6502

SOURCE = HERE.parents[1] / 'appleII/images/wizardry_i/snafaru_restored_scenario.dsk'


class CompressionTests(unittest.TestCase):
    def test_roundtrips_and_partial_output(self):
        rng = random.Random(192)
        samples = [b'', b'x', b'A' * 8192, bytes(range(256)) * 32,
                   rng.randbytes(512), rng.randbytes(1800)]
        # Exercise offsets over 1 KB and overlapping matches.
        prefix = rng.randbytes(1700)
        samples.append(prefix + prefix + b'ABC' * 800)
        for data in samples:
            encoded = compress.lzss_encode(data)
            if encoded is not None:
                self.assertLess(len(encoded), len(data))
                self.assertEqual(compress.lzss_decode(encoded, len(data)), data)
                for size in (1, 2, len(data) - 1):
                    self.assertEqual(compress.lzss_decode(encoded, size), data[:size])

    def test_zx02_roundtrips_and_partial_output(self):
        rng = random.Random(2)
        prefix = rng.randbytes(2600)
        for data in (b'A' * 8192, bytes(range(256)) * 32, prefix + prefix + b'abc' * 900):
            encoded = zx02.encode(data)
            self.assertIsNotNone(encoded)
            self.assertEqual(zx02.decode(encoded), data)
            for size in (1, 2, 128, len(data) - 1):
                self.assertEqual(zx02.decode(encoded, size), data[:size])

    def test_legacy_wzc2_import(self):
        original = PascalDisk.open(SOURCE)
        volume = build.volume_bytes(original)
        build.patch_volume(volume, original, 'WIZARDRY.CODE')
        def legacy_unit(data):
            encoded = compress.lzss_encode(data)
            return (data, True) if encoded is None else (encoded, False)
        with patch.object(build, 'MAP_MAGIC', b'WZC2'), patch.object(build, 'compress_unit', legacy_unit):
            body, _ = build.compress_scenario(volume, original, [])
        with tempfile.TemporaryDirectory() as directory:
            legacy = Path(directory) / 'legacy.atr'
            build.write_atr(legacy, body)
            imported = build.atr_scenario(legacy)
            self.assertEqual(imported.read('SCENARIO.DATA'), original.read('SCENARIO.DATA'))
        # Also check the previous branch build when that local fixture exists.
        legacy = HERE / 'build/legacy_wzc2_disk2.atr'
        if legacy.exists():
            imported = build.atr_scenario(legacy)
            self.assertEqual(imported.read('SCENARIO.DATA'), original.read('SCENARIO.DATA'))

    def test_volume_reconstruction_and_capacity(self):
        disk = PascalDisk.open(SOURCE)
        volume = build.volume_bytes(disk)
        build.patch_volume(volume, disk, 'WIZARDRY.CODE')
        body, layout = build.compress_scenario(volume, disk, [b'AB' * 832])
        read = build.volume_blocks(body, 0)
        self.assertEqual(b''.join(read(i) for i in range(280)), volume)
        self.assertEqual(len(body), 1440 * 128)
        self.assertLess(layout['CONTENT_BYTES'], len(body))
        with self.assertRaises(SystemExit):
            build.compress_scenario(volume, disk, [random.Random(3).randbytes(1664)] * 300)

    def test_writable_caches_include_all_maze_levels(self):
        writable = build.writable_data_blocks(PascalDisk.open(SOURCE))
        self.assertTrue(set(range(6, 26)) <= writable)
        self.assertTrue(set(range(68, 94)) <= writable)


MANIFEST = HERE / 'build/test_pce_disk1.layout.json'


@unittest.skipUnless(MANIFEST.exists(), 'build.py --disk2 --pictures monster --testmode --out test_pce.atr')
class AssembledCompressionTests(unittest.TestCase):
    def setUp(self):
        self.layout = json.loads(MANIFEST.read_text())
        self.labels = {line.split()[2].lstrip('.'): int(line.split()[1], 16)
                       for line in (HERE / 'build/test_pce_disk1.labels.txt').read_text().splitlines()}
        self.mem = bytearray(65536)
        disk1 = (HERE / 'build/test_pce_disk1.atr').read_bytes()[16:]
        self.body = bytearray((HERE / 'build/test_pce_disk2.atr').read_bytes()[16:])
        for address, first, count in ((0x06FA, 1, 'BOOT_SECTORS'), (0xB000, self.layout['TABLE_SECTOR'], 'TABLE_SECTORS'),
                                      (0x4000, self.layout['GOVL_SECTOR'], 'GOVL_SECTORS'),
                                      (self.layout['COMP_ADDR'], self.layout['COMP_SECTOR'], 'COMP_SECTORS')):
            data = disk1[(first - 1) * 128:(first - 1 + self.layout[count]) * 128]
            self.mem[address:address + len(data)] = data
        if self.layout.get('MUSIC'):
            start = (self.layout['MUSA_SECTOR'] - 1) * 128
            data = disk1[start:start + self.layout['MUSA_SECTORS'] * 128]
            at = self.layout['MUSIC_PLAYER']
            self.mem[at:at + len(data)] = data
        self.mem[0xD301] = 1
        self.word(self.labels['volbase'], 1)
        self.word(self.labels['codebase'], 1)
        self.cpu = CPU6502(self.mem, io_read=lambda a: self.mem[a],
                          io_write=lambda a, v: self.mem.__setitem__(a, v))
        self.cpu.traps[0xE459] = self.sio
        self.transfers = []
        self.disk = PascalDisk.open(SOURCE)
        self.volume = build.volume_bytes(self.disk)
        build.patch_volume(self.volume, self.disk, 'WIZARDRY.CODE')

    def word(self, address, value):
        self.mem[address:address + 2] = struct.pack('<H', value)

    def sio(self, cpu):
        # The real OS must be visible whenever SIO is called.
        self.assertTrue(self.mem[0xD301] & 1)
        sector = int.from_bytes(self.mem[0x30A:0x30C], 'little')
        buffer = int.from_bytes(self.mem[0x304:0x306], 'little')
        self.assertTrue(1 <= sector <= 1440, sector)
        self.assertLess(buffer, 0xC000)
        at = (sector - 1) * 128
        if self.mem[0x302] == 0x57:
            self.body[at:at + 128] = self.mem[buffer:buffer + 128]
        else:
            self.mem[buffer:buffer + 128] = self.body[at:at + 128]
        self.transfers.append((self.mem[0x302], sector))
        cpu.n = 0
        cpu.c = 0

    def call(self, label):
        self.cpu.push(0xFF)
        self.cpu.push(0xEF)
        self.cpu.run(self.labels[label], 0xFFF0)
        self.assertEqual(self.cpu.s, 0xFF)
        self.assertEqual(self.mem[0xD301], 1)

    def request(self, block, size, label='disk_read'):
        self.word(0x94, 0x8000)
        self.word(0x98, block)
        self.word(0xA9, size)
        self.word(0x9C, 0xABCD)       # load_segment relies on t6 surviving
        self.mem[0xAD] = 0
        self.mem[0x7FFF] = 0xA5
        self.mem[0x8000 + size] = 0x5A
        self.call(label)
        self.assertEqual(self.mem[0x9C:0x9E], b'\xCD\xAB')
        self.assertEqual(self.mem[0x7FFF], 0xA5)
        self.assertEqual(self.mem[0x8000 + size], 0x5A)
        return bytes(self.mem[0x8000:0x8000 + size])

    def test_every_segment_exact_and_bounded(self):
        first = self.disk.entry('WIZARDRY.CODE').first_block
        for seg in CodeFile(self.disk.read('WIZARDRY.CODE')).segments:
            with self.subTest(segment=seg.name):
                block = first + seg.block
                self.assertEqual(self.request(block, seg.length, 'disk_read_code'),
                                 self.volume[block * 512:block * 512 + seg.length])
                self.assertEqual(self.mem[0xAD], 0)

    def test_all_data_messages_and_partial_cache_reads(self):
        for block in list(range(7)) + list(range(149, 280)):
            with self.subTest(block=block):
                self.assertEqual(self.request(block, 512), self.volume[block * 512:(block + 1) * 512])
                self.assertEqual(self.mem[0xAD], 0)
        for block, size in ((149, 1024), (155, 800), (217, 1024), (265, 129), (279, 511)):
            self.assertEqual(self.request(block, size), self.volume[block * 512:block * 512 + size])

    def test_writes_preserve_other_blocks_and_pictures(self):
        writable = build.writable_data_blocks(self.disk)
        wanted = bytearray(self.volume)
        for index in sorted(writable):
            payload = random.Random(index).randbytes(512)
            self.mem[0x8000:0x8200] = payload
            self.request(149 + index, 512, 'disk_write')
            self.assertEqual(self.mem[0xAD], 0)
            wanted[(149 + index) * 512:(150 + index) * 512] = payload
        read = build.volume_blocks(self.body, 0)
        self.assertEqual(b''.join(read(i) for i in range(280)), wanted)
        end = self.layout['VOLUME_BYTES']
        original = (HERE / 'build/test_pce_disk2.atr').read_bytes()[16:]
        self.assertEqual(self.body[end:], original[end:])

    def test_partial_write_and_saved_atr_import(self):
        block = 149 + 84
        payload = b'ALICE-ROUNDTRIP!'
        self.mem[0x8000:0x8000 + len(payload)] = payload
        self.request(block, len(payload), 'disk_write')
        self.assertEqual(self.mem[0xAD], 0)
        wanted = bytearray(self.volume)
        wanted[block * 512:block * 512 + len(payload)] = payload
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'saved.atr'
            build.write_atr(path, self.body)
            disk = build.atr_scenario(path)
            self.assertEqual(build.volume_bytes(disk), wanted)

    def test_positive_enemy_counter_is_writable(self):
        from wizardry_scenario import Scenario
        scenario = Scenario(self.disk)
        offset = scenario.record_offset('ZENEMY', 99) + 148
        data_first = self.disk.entry('SCENARIO.DATA').first_block
        volume = bytearray(self.volume)
        struct.pack_into('<h', volume, data_first * 512 + offset, 1)
        # Reconstruct a normal PascalDisk with that positive counter.
        from tests.test_disk2 import scenario_from_disk2
        modified = scenario_from_disk2(b'\0' * 16 + volume)
        self.body, _ = build.compress_scenario(volume, modified, [])
        cache = scenario.first_block['ZENEMY'] + 2 * (99 // scenario.per_cache['ZENEMY'])
        payload = bytes([0xAA]) * 1024
        self.mem[0x8000:0x8400] = payload
        self.request(data_first + cache, 1024, 'disk_write')
        self.assertEqual(self.mem[0xAD], 0)
        read = build.volume_blocks(self.body, 0)
        self.assertEqual(read(data_first + cache) + read(data_first + cache + 1), payload)

    def test_sio_failure_and_compressed_write_rejection(self):
        self.request(150, 512, 'disk_write')
        self.assertEqual(self.mem[0xAD], 16)
        self.assertTrue(all(command == 0x52 for command, _ in self.transfers))
        self.mem[self.labels['map_valid']] = 0
        def failed(cpu):
            cpu.n = 1
        self.cpu.traps[0xE459] = failed
        self.request(149, 512)
        self.assertEqual(self.mem[0xAD], 16)

    def test_failed_verification_cannot_accept_stale_directory(self):
        self.call('verify_scen')
        self.assertEqual(self.cpu.c, 1)
        # Keep a valid scenario directory in SECBUF, then make SIO fail.
        def failed(cpu):
            cpu.n = 1
        self.cpu.traps[0xE459] = failed
        self.call('verify_scen')
        self.assertEqual(self.cpu.c, 0)
        self.assertEqual(self.mem[0xAD], 16)

    def test_every_picture_decodes_exactly(self):
        import pickle
        import pictures
        from wizardry_scenario import Scenario
        cache = pickle.loads((HERE / 'build/pictures.cache').read_bytes())
        records = cache[pictures.cache_key(Scenario(self.disk), 'monster')][0]
        for i, record in enumerate(records):
            with self.subTest(picture=i):
                self.word(0xAB, self.layout['sector'][i])
                self.mem[0xFF] = self.layout['skip'][i]
                self.mem[0xDB] = self.layout['len'][i][1]
                self.word(0xFD, self.layout['PICTURE_LENS'][i] & 0x7FFF)
                self.cpu.a = 1
                self.call('comp_call')
                self.assertEqual(self.mem[self.layout['PICOUT']:self.layout['PICOUT'] + len(record)], record)

    def test_decoder_yields_preserve_output_and_registers(self):
        read, write = self.cpu.read, self.cpu.write
        clock_reads, resumes = [], []
        def video_clock(address):
            if address == 0xD40B:
                clock_reads.append(address)
                # Periodically force a visible scanline, followed by a blank.
                return 40 if len(clock_reads) % 5 == 0 else 127
            return read(address)
        def bank_switch(address, value):
            if address == 0xD301 and value & 1 and not self.mem[address] & 1:
                resumes.append(address)
            write(address, value)
        self.cpu.read, self.cpu.write = video_clock, bank_switch
        for block, size in ((175, 512), (265, 512), (279, 129)):
            self.assertEqual(self.request(block, size), self.volume[block * 512:block * 512 + size])
        self.assertGreater(len(resumes), 50)
