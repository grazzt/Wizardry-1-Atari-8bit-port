"""Optional OP roster: original-game parsing, spell books, saves and maze entry."""
import json
import struct
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / 'tools'))
import build
import party
from harness import LIBRARY
from pvm.tests.test_pvm import IMAGES, START, machine
from pvm.cpu6502 import CPU6502
from ucsd.disk import PascalDisk
from wizardry_scenario import RECORD_SIZE, Scenario

SOURCE = IMAGES / 'snafaru_restored_scenario.dsk'
JOIN = 'G' + ''.join('A' + name + '\r\r' for name, _ in party.MEMBERS)


class PartyTests(unittest.TestCase):
    def test_only_vacant_character_records_change(self):
        original = PascalDisk.open(SOURCE)
        saved = original.image
        seeded, members = party.seed(original)
        before, after = Scenario(original), Scenario(seeded)
        roster = list(after.roster())
        for member in members:
            self.assertFalse(roster[member['slot']][2])
        allowed = set()
        for member in members:
            at = before.record_offset('ZCHAR', member['slot'])
            allowed.update(range(at, at + RECORD_SIZE['ZCHAR']))
        changes = {i for i, (a, b) in enumerate(zip(before.data, after.data)) if a != b}
        self.assertTrue(changes <= allowed)
        self.assertEqual(original.image, saved)
        for name in ('WIZARDRY.CODE', 'SCENARIO.MESGS'):
            self.assertEqual(seeded.read(name), original.read(name))

    def test_preserves_existing_characters_and_uses_unique_names(self):
        first, members = party.seed(PascalDisk.open(SOURCE))
        second, added = party.seed(first)
        before, after = Scenario(first), Scenario(second)
        for member in members:
            self.assertEqual(before.record('ZCHAR', member['slot']), after.record('ZCHAR', member['slot']))
        self.assertTrue({m['name'] for m in members}.isdisjoint(m['name'] for m in added))
        self.assertEqual([m['slot'] for m in added], list(range(6, 12)))

    def test_full_roster_fails_without_changing_source(self):
        original = PascalDisk.open(IMAGES / 'wizardry_i_scenario.dsk')
        saved = original.image
        with self.assertRaisesRegex(SystemExit, 'six vacant roster slots'):
            party.seed(original)
        self.assertEqual(original.image, saved)

    def test_game_reads_stats_spell_books_and_enters_maze(self):
        seeded, members = party.seed(PascalDisk.open(SOURCE))
        vm = machine(seeded)
        vm.send(START + JOIN)
        for member in members:
            self.assertIn(member['name'], vm.console.text())
        vm.send('\rEM6')  # leave tavern, edge, maze camp, inspect Merlin
        self.assertIn('GOLD      1000000', vm.console.text())
        self.assertIn('LEVEL  50', vm.console.text())
        self.assertIn('HITS 999/999', vm.console.text())
        self.assertIn('MAGE 9/9/9/9/9/9/9', vm.console.text())
        self.assertIn('PRIEST 9/9/9/9/9/9/9', vm.console.text())
        for stat in ('STRENGTH', 'I.Q.', 'PIETY', 'VITALITY', 'AGILITY', 'LUCK'):
            self.assertRegex(vm.console.text(), stat.replace('.', r'\.') + r'\s+18')
        vm.send('RM')
        self.assertIn('TILTOWAIT', vm.console.text())
        vm.send('LP')
        self.assertIn('KADORTO', vm.console.text())
        vm.send('LLLL')  # leave priest book, spell books, inspection and camp
        self.assertIn('RUNNER', vm.loaded_names())
        self.assertTrue(vm.display['graphics'])
        saved = Scenario(PascalDisk(bytes(vm.units[4].image)))
        for member in members:
            row = list(saved.roster())[member['slot']]
            self.assertEqual(row[1], member['name'])
            self.assertTrue(row[2], 'maze party must be persisted as OUT')
            self.assertEqual(saved.record('ZCHAR', member['slot'])[58:60], b'\0\0')


MANIFEST = HERE / 'build/test_party_disk1.layout.json'


@unittest.skipUnless(LIBRARY.exists() and MANIFEST.exists(),
    'build.py --disk2 --party --pictures monster --testmode --no-title --out test_party.atr')
class AtariPartyTests(unittest.TestCase):
    def formed_run(self):
        from lockstep import Lockstep
        layout = json.loads(MANIFEST.read_text())
        reference = build.atr_scenario(HERE / 'build/test_party_disk2.atr')
        run = Lockstep(atr=HERE / 'build/test_party_disk1.atr',
                       disk2=HERE / 'build/test_party_disk2.atr',
                       scenario=reference, title=False, sio_patch=False)
        self.addCleanup(run.close)
        run.settle()
        self.assertTrue(run.at_prompt)
        run.swap_disk()
        run.atari.type('\r')
        run.settle()
        self.assertFalse(run.at_prompt)
        # The reference uses the original tavern to assemble the same party;
        # the Atari reaches this screen using only the two startup Returns.
        for key in START:
            run.atari.type(key)
            run.settle()
        joins = 'G' + ''.join('A' + m['name'] + '\r\r' for m in layout['PARTY']) + '\r'
        run.vm.send(START + joins)
        run.typed = run.vm.console.keys_read
        for index, address in enumerate((0x47A, 0x4FA, 0x57A, 0x5FB)):
            run.atari.memory[0xC0 + index] = run.vm.mem[address]
        self.assertEqual(run.vm.console.text(), run.atari.text_memory())
        self.assertEqual(run.atari.peek(run.labels['party_formed']), 1)
        self.assertEqual(run.atari.peek(run.labels['party_failed']), 0)
        return run

    def test_party_spells_maze_and_save_through_real_disk_swap(self):
        from lockstep import bitmap_diff, diff
        from tests.test_disk2 import scenario_from_disk2
        run = self.formed_run()
        keys = 'EM6RMLPLLLL'  # directly to maze; inspect both books, leave camp
        for index, key in enumerate(keys):
            ref, actual = run.step(key)
            self.assertFalse(run.error, f'error at key {index}')
            self.assertEqual(ref, actual, f'key {index}:\n{diff(ref, actual)}')
            self.assertEqual(*run.graphics)
            if run.graphics[0]:
                self.assertEqual(bitmap_diff(run.vm, run.atari), [])
        self.assertIn('RUNNER', run.vm.loaded_names())
        self.assertTrue(run.graphics[1])
        self.assertEqual(run.atari.peek(run.labels['ml_failed']), 0)
        expected = PascalDisk(bytes(run.vm.units[4].image)).read('SCENARIO.DATA')
        actual = scenario_from_disk2(run.disk2.read_bytes()).read('SCENARIO.DATA')
        self.assertEqual(actual, expected)

    def test_werdna_fight_gives_the_amulet_without_error(self):
        """Regression for the CALCULAT divide by zero (fixed drops have RANGE 0): replay the
        whole route to Werdna on pvm and the Atari, comparing screens after every key."""
        from lockstep import diff
        keys = json.loads((HERE / 'tests/werdna_keys.json').read_text())['keys']
        run = self.formed_run()
        seen = []
        for index, key in enumerate(keys):
            ref, screen = run.step(key)
            seen.append(screen)
            self.assertFalse(run.error, f'error {[hex(run.atari.peek(0x580 + n)) for n in range(6)]} at key {index}')
            self.assertEqual(ref, screen, f'key {index}:\n{diff(ref, screen)}')
        self.assertTrue(any('MERLIN HUMAN' in s and '1)?AMULET' in s for s in seen))   # item 94, unidentified

    def test_party_does_not_reform_when_removed_at_tavern(self):
        run = self.formed_run()
        for key in 'G' + 'R1' * 6 + '\r':
            reference, actual = run.step(key)
            self.assertEqual(reference, actual)
            self.assertFalse(run.error)
        self.assertNotIn('VANGUARD', run.atari.text_memory())
        self.assertEqual(run.atari.peek(run.labels['party_formed']), 1)


@unittest.skipUnless(MANIFEST.exists(), 'build the auto-party test images')
class NativePartyTests(unittest.TestCase):
    def setUp(self):
        from tests.test_compression import AssembledCompressionTests
        self.runtime = AssembledCompressionTests()
        self.runtime.mem = bytearray(65536)
        self.runtime.transfers = []
        self.layout = json.loads(MANIFEST.read_text())
        self.runtime.layout = self.layout
        self.labels = {r.split()[2].lstrip('.'): int(r.split()[1], 16)
                       for r in (HERE / 'build/test_party_disk1.labels.txt').read_text().splitlines()}
        self.runtime.labels = self.labels
        self.mem = self.runtime.mem
        self.mem[0xD301] = 1
        self.runtime.cpu = CPU6502(self.mem, io_read=lambda a: self.mem[a],
                                  io_write=lambda a, v: self.mem.__setitem__(a, v))
        self.runtime.cpu.traps[0xE459] = self.runtime.sio
        body = (HERE / 'build/test_party_disk1.atr').read_bytes()[16:]
        for address, first, count in ((0x06FA, 1, 'BOOT_SECTORS'),
                (0xB000, self.layout['TABLE_SECTOR'], 'TABLE_SECTORS'),
                (0x4000, self.layout['GOVL_SECTOR'], 'GOVL_SECTORS'),
                (self.layout['COMP_ADDR'], self.layout['COMP_SECTOR'], 'COMP_SECTORS')):
            data = body[(first - 1) * 128:(first - 1 + self.layout[count]) * 128]
            self.mem[address:address + len(data)] = data
        self.runtime.body = bytearray((HERE / 'build/test_party_disk2.atr').read_bytes()[16:])
        self.runtime.word(self.labels['volbase'], 1)
        self.runtime.word(self.labels['codebase'], 1)
        self.scenario = Scenario(build.atr_scenario(HERE / 'build/test_party_disk2.atr'))
        self.runtime.word(0x86, 0xA000)  # p-machine program frame
        self.runtime.word(0x88, 0x9800)  # transient buffer must be released
        self.mem[0xA0:0xA2] = bytes([16, 1])
        self.mem[0xAD] = 7

    def edit_record(self, slot, field, data):
        offset = self.scenario.record_offset('ZCHAR', slot) + field
        block, within = divmod(offset, 512)
        entry = (self.layout['MAP_START'] - 1) * 128 + self.layout['MAP_DATA'] + block * 3
        sector, control = struct.unpack_from('<HB', self.runtime.body, entry)
        self.assertTrue(control & 0x80)
        at = (sector - 1) * 128 + (control & 127) + within
        self.runtime.body[at:at + len(data)] = data

    def form(self):
        self.runtime.call('party_auto_form')
        self.assertEqual(self.mem[0x88:0x8A], b'\0\x98')
        self.assertEqual(self.mem[0xAD], 7)
        return int.from_bytes(self.mem[0xA010:0xA012], 'little')

    def test_reads_current_saved_stats_and_preserves_other_data(self):
        self.edit_record(0, 52, struct.pack('<3h', 4321, 12, 0))
        self.edit_record(0, 134, struct.pack('<h', 777))
        before = build.volume_blocks(self.runtime.body, 0)
        data_before = b''.join(before(block) for block in range(280))
        self.assertEqual(self.form(), 6)
        self.assertEqual(self.mem[0xA09E + 52:0xA09E + 58], struct.pack('<3h', 4321, 12, 0))
        self.assertEqual(self.mem[0xA09E + 134:0xA09E + 136], struct.pack('<h', 777))
        read = build.volume_blocks(self.runtime.body, 0)
        data_after = b''.join(read(block) for block in range(280))
        expected = bytearray(data_before)
        first = build.atr_scenario(HERE / 'build/test_party_disk2.atr').entry('SCENARIO.DATA').first_block
        for member in self.layout['PARTY']:
            offset = first * 512 + self.scenario.record_offset('ZCHAR', member['slot'])
            expected[offset + 32] = 1
        self.assertEqual(data_after, expected)

    def test_rejects_out_dead_disbanded_or_replaced_member_before_writing(self):
        for field, value in ((32, b'\1\0'), (40, b'\5\0'), (204, b'\1\0'), (1, b'X')):
            with self.subTest(field=field):
                self.setUp()
                self.edit_record(5, field, value)
                before = bytes(self.runtime.body)
                self.assertEqual(self.form(), 0)
                self.assertEqual(self.mem[self.labels['party_formed']], 0)
                self.assertEqual(bytes(self.runtime.body), before)
                self.assertFalse(any(command == 0x57 for command, _ in self.runtime.transfers))

    def test_read_failure_preserves_ioresult_and_does_not_form_party(self):
        def failed(cpu):
            cpu.n = 1
        self.runtime.cpu.traps[0xE459] = failed
        before = bytes(self.runtime.body)
        self.assertEqual(self.form(), 0)
        self.assertEqual(self.mem[self.labels['party_failed']], 16)
        self.assertEqual(bytes(self.runtime.body), before)

    def test_write_failure_does_not_publish_partial_party(self):
        def fail_writes(cpu):
            if self.mem[0x302] == 0x57:
                cpu.n = 1
            else:
                self.runtime.sio(cpu)
        self.runtime.cpu.traps[0xE459] = fail_writes
        before = bytes(self.runtime.body)
        self.assertEqual(self.form(), 0)
        self.assertEqual(self.mem[self.labels['party_failed']], 16)
        self.assertEqual(bytes(self.runtime.body), before)
