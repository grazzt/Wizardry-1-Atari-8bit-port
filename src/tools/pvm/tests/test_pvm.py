"""End-to-end tests: run the real WIZARDRY.CODE on the host p-machine.

    cd tools && python3 -m unittest discover -s pvm/tests -t .
"""
import hashlib
from pathlib import Path
import random
import tempfile
import unittest

from ucsd.codefile import CodeFile
from ucsd.disk import PascalDisk
from pvm.console import Console
from pvm.machine import DiskUnit, PMachine

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


if __name__ == '__main__':
    unittest.main()
