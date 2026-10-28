"""End-to-end tests: run the real WIZARDRY.CODE on the host p-machine.

    cd tools && python3 -m unittest discover -s pvm/tests -t .
"""
import hashlib
from pathlib import Path
import random
import tempfile
import unittest

from ucsd import pcode
from ucsd.codefile import CodeFile
from ucsd.disk import PascalDisk
from pvm.console import Console
from unittest import mock

from pvm import patches
from pvm.machine import DiskUnit, PMachine, VMError, s16

PROJECT = Path(__file__).resolve().parents[3]
IMAGES = PROJECT / 'appleII/images/wizardry_i'
BOOT = PascalDisk.open(IMAGES / 'wizardry_i_boot.dsk')
CODE = CodeFile(BOOT.read('WIZARDRY.CODE'))

# Start-up: RETURN at "SCENARIO MASTER IN DRV 1", RETURN at "MASTER/DUPLICATE".
START = '\r\r'
CREATE_ALICE = 'ETALICE\rY\r\rAA' + '+' * 10 + '\x1bAY'   # human, good, ST 18, fighter, keep
LEAVE_GAME = '\rCEL'                                       # training -> castle -> edge -> leave


def machine(scenario=IMAGES / 'snafaru_restored_scenario.dsk', seed=1):
    disk = PascalDisk.open(scenario) if isinstance(scenario, Path) else scenario
    return PMachine(CODE, {4: DiskUnit(disk), 5: DiskUnit(BOOT)}, Console(), key_seed=seed)


def title_machine(seed=1, scenario=None):
    """Start with SYSTEM.STARTUP (title, options), which chains to the game."""
    scenario = scenario or PascalDisk.open(IMAGES / 'snafaru_restored_scenario.dsk')
    return PMachine(CODE, {4: DiskUnit(scenario), 5: DiskUnit(BOOT)}, Console(), key_seed=seed,
                    startup=CodeFile(BOOT.read('SYSTEM.STARTUP')))


def out_scenario():
    """A scenario disk with ALICE "OUT": the machine was switched off while
    she was in the maze."""
    vm = machine()
    vm.send(START + CREATE_ALICE + LEAVE_GAME)
    vm = machine(PascalDisk(bytes(vm.units[4].image), 'saved'))
    vm.send(START + 'GAALICE\r\r\rEML')                # party, edge of town, maze, leave camp
    return PascalDisk(bytes(vm.units[4].image), 'out')


# Title, U)TILITIES, R)ECOVER, RETURN to begin, RETURN at "PLACE SCENARIO IN DRIVE 1".
RECOVER = [' ', 'U', 'R', '\r', '\r']


def roster_names(image_bytes):
    import wizardry_scenario
    with tempfile.NamedTemporaryFile(suffix='.dsk') as f:
        f.write(image_bytes)
        f.flush()
        return [r[1] for r in wizardry_scenario.Scenario(f.name).roster()]


class GameTests(unittest.TestCase):
    def test_boots_to_castle(self):
        vm = machine()
        self.assertEqual(vm.send(START), 'input')
        screen = vm.console.text()
        self.assertIn('! CASTLE                        MARKET !', screen)
        self.assertIn("THE A)DVENTURER'S INN, G)ILGAMESH'", screen)
        self.assertEqual(vm.loaded_names(), ['WIZARDRY', 'CASTLE'])

    def test_create_save_and_reload_character(self):
        vm = machine()
        vm.send(START + CREATE_ALICE)
        self.assertIn('TRAINING GROUNDS', vm.console.text())
        vm.send(LEAVE_GAME)
        self.assertIn('PRESS [RETURN] FOR MORE WIZARDRY', vm.console.text())
        saved = bytes(vm.units[4].image)
        self.assertEqual(roster_names(saved)[0], 'ALICE')

        disk = PascalDisk(saved, 'saved')
        vm = machine(disk)
        vm.send(START + 'GAALICE\r\r')                     # Gilgamesh's: add ALICE, no password
        self.assertIn(' 1 ALICE           G-FIG 10    9    9', vm.console.text())

    def test_maze_and_battle(self):
        vm = machine()
        vm.send(START + CREATE_ALICE + LEAVE_GAME)
        vm = machine(PascalDisk(bytes(vm.units[4].image), 'saved'))
        vm.send(START + 'GAALICE\r\r\rEML')                # party, edge of town, maze, leave camp
        self.assertTrue(vm.display['graphics'])
        self.assertIn('RUNNER', vm.loaded_names())

        # Wander (answering N to stairs prompts) until an encounter starts.
        walk = random.Random(3)                           # meets monsters after ~20 moves
        for _ in range(400):
            vm.send(walk.choice('FFFFLR') + 'N')
            if 'CUTIL' in vm.loaded_names():
                break
        else:
            self.fail('no encounter')

        messages = []
        original = vm.call

        def spy(seg, proc):
            if (seg, proc) == (1, 23):                    # PRINTSTR
                messages.append(vm.pstring(vm.stack[-1]))
            original(seg, proc)
        vm.call = spy
        for _ in range(30):
            vm.send('\r')
            if 'CUTIL' not in vm.loaded_names():
                break
            vm.send('F')
        text = ' '.join(messages)
        self.assertRegex(text, r'(SWINGS|THRUSTS|STABS|CHOPS|SLASHES)')
        self.assertIn('DAMAGE', text)

    def test_keys_one_at_a_time_match_all_at_once(self):
        # Running out of keys inside a call must not change the outcome.
        whole = machine(seed=3)
        whole.send(START + CREATE_ALICE)
        split = machine(seed=3)
        for key in START + CREATE_ALICE:
            split.send(key)
        self.assertEqual(split.console.text(), whole.console.text())
        self.assertEqual(bytes(split.mem), bytes(whole.mem))

    def test_title_options_and_chain(self):
        vm = title_machine()
        vm.send(' ')                                       # any key ends the title animation
        self.assertIn('VERSION 2.1 OF 22-JAN-82', vm.console.text())
        self.assertIn('S)TART GAME  U)TILITIES  T)ITLE PAGE', vm.console.text())
        self.assertEqual(vm.program, 'SYSTEM.STARTUP')
        vm.send('S')                                       # start: chains to WIZARDRY.CODE
        self.assertEqual(vm.program, 'WIZARDRY.CODE')
        self.assertIn('SCENARIO MASTER IN DRV 1', vm.console.text())
        vm.send('\r\r')
        self.assertIn('! CASTLE', vm.console.text())

    def test_recover_out_character(self):
        out = out_scenario()
        vm = machine(out)
        vm.send(START + 'ET*ROSTER\r')
        self.assertIn('ALICE LEVEL 1 HUMAN FIGHTER (OK) OUT', vm.console.text())
        vm = title_machine(scenario=out)
        for keys in RECOVER:                              # drive 1 becomes the scenario disk
            vm.send(keys)
        self.assertIn('ALICE SAVED', vm.console.text())
        vm.send('\r')
        vm.send('L')                                      # and the boot disk again
        self.assertIn('S)TART GAME  U)TILITIES  T)ITLE PAGE', vm.console.text())
        vm.send('S')
        vm.send(START + 'ET*ROSTER\r')
        self.assertIn('ALICE LEVEL 1 HUMAN FIGHTER (OK)', vm.console.text())
        self.assertNotIn(' OUT', vm.console.text())

    def test_deterministic(self):
        def run():
            vm = machine(seed=5)
            vm.send(START + CREATE_ALICE)
            return hashlib.sha256(bytes(vm.mem)).hexdigest(), vm.instructions
        self.assertEqual(run(), run())


def calculat(tries, aveamt, minadd, patched=True, rng=0):
    """Call REWARDS.27 (CALCULAT) directly: push TRIES, AVEAMT, MINADD and the two result words.
    `patched=False` runs the code without the CALCULAT patch."""
    code, keep = CODE, patches.PATCHES['WIZARDRY.CODE']
    if not patched:
        code, keep = CodeFile(BOOT.read('WIZARDRY.CODE')), keep[:1]
    with mock.patch.dict(patches.PATCHES, {'WIZARDRY.CODE': keep}):
        vm = PMachine(code, {4: DiskUnit(PascalDisk.open(IMAGES / 'snafaru_restored_scenario.dsk')),
                             5: DiskUnit(BOOT)}, Console())
    for addr in (0x047A, 0x04FA, 0x057A, 0x05FB):             # the game's RNG state
        vm.mem[addr] = (rng * 37 + addr) & 0xFF
    top = vm.frame
    for value in (tries, aveamt, minadd, 0, 0):
        vm.push(value)
    vm.call(19, 27)
    for _ in range(10_000):
        if vm.frame is top:
            return s16(vm.pop())
        vm.step()
    raise AssertionError('CALCULAT did not return')


class CalculatTests(unittest.TestCase):
    """The divide-by-zero patch for the fixed item drops (Werdna's Amulet)."""

    def test_unpatched_zero_range_is_error_6(self):
        with self.assertRaises(VMError) as raised:
            calculat(1, 0, 1, patched=False)
        self.assertEqual(raised.exception.code, 6)

    def test_zero_range_is_a_fixed_drop(self):
        # ITEMREWD adds MININDX to CALCULAT(1, RANGE, 1): a fixed drop must come out as MININDX.
        for tries, minadd in ((1, 1), (1, 7), (3, 1), (0, 5)):
            self.assertEqual(calculat(tries, 0, minadd), 0)
        self.assertEqual(calculat(1, -3, 1), 0)

    def test_no_tries_returns_minadd(self):
        self.assertEqual(calculat(0, 6, 5), 5)

    def test_patched_procedure_decodes_whole(self):
        seg = CODE.segment(19)
        proc = seg.procedure(27)
        starts, pc = set(), proc.enter
        while pc <= proc.exit:
            ins = pcode.decode(seg.code, pc, proc.jtab)
            starts.add(pc)
            pc = ins.end
        self.assertEqual(pc, proc.exit + 2)                    # RNP 1 is the last instruction
        for pc in sorted(starts):
            for target in pcode.decode(seg.code, pc, proc.jtab).targets:
                self.assertIn(target, starts)

    def test_positive_range_rolls_as_before(self):
        rolls = set()
        for rng in range(12):
            for tries, aveamt, minadd in ((1, 6, 1), (3, 6, 0), (2, 100, 5), (1, 15, 1)):
                expected = calculat(tries, aveamt, minadd, patched=False, rng=rng)
                self.assertEqual(calculat(tries, aveamt, minadd, rng=rng), expected)
                rolls.add(expected)
        self.assertGreater(len(rolls), 4)                     # the RNG state really varies


if __name__ == '__main__':
    unittest.main()
