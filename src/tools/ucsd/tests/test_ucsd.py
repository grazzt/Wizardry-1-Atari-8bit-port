"""Regression tests against the project's Wizardry I images and Ewers's listings.

    cd tools && python3 -m unittest discover -s ucsd/tests -t .
"""
import io
from contextlib import redirect_stdout
from pathlib import Path
import unittest

from ucsd.__main__ import main
from ucsd.codefile import CodeFile
from ucsd.disk import PascalDisk, decode_text
from ucsd import m6502, pcode

PROJECT = Path(__file__).resolve().parents[3]
IMAGES = PROJECT / 'appleII/images/wizardry_i'
EWERS = PROJECT / 'appleII/source/ewers_wizardry_i'
BOOT = IMAGES / 'wizardry_i_boot.dsk'


class DiskTests(unittest.TestCase):
    def test_boot_catalog(self):
        disk = PascalDisk.open(BOOT)
        self.assertEqual(disk.volume, 'WBV2.1')
        self.assertEqual(disk.order, 'dos')
        self.assertEqual([e.name for e in disk.entries],
                         ['WIZARDRY.CODE', 'RTSTRP.APPLE', 'SYSTEM.PASCAL', 'SYSTEM.LIBRARY',
                          'SYSTEM.MISCINFO', 'WT', 'SYSTEM.STARTUP'])
        self.assertEqual(len(disk.read('WIZARDRY.CODE')), 73216)

    def test_code_identical_on_both_disks(self):
        scenario = PascalDisk.open(IMAGES / 'wizardry_i_scenario.dsk')
        self.assertEqual(scenario.read('WIZARDRY.CODE'), PascalDisk.open(BOOT).read('WIZARDRY.CODE'))

    def test_text_file(self):
        text = decode_text(PascalDisk.open(EWERS / 'WizardryCode/Wiz1D.DSK').read('RANDOM.TEXT'))
        self.assertTrue(text.startswith(' .FUNC RANDOM,0'))
        self.assertIn('USES $47A, $4FA, $57A, $5FB', text)


class CodeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.code = CodeFile(PascalDisk.open(BOOT).read('WIZARDRY.CODE'))

    def test_segments(self):
        self.assertEqual([s.number for s in self.code.segments], [1] + list(range(7, 21)))
        self.assertEqual(self.code.segment('UTILITIE').length, 7766)

    def test_every_pcode_procedure_decodes(self):
        count = 0
        for seg in self.code.segments:
            for proc in seg.procedures:
                if not proc.native:
                    pcode.disassemble(seg.code, proc)
                    count += 1
        self.assertEqual(count, 417)

    def test_case_with_negative_labels(self):
        # SWINGASW's main body is CASE ATTACKTY OF -5..-1.
        seg = self.code.segment('SWINGASW')
        xjp = next(i for i in pcode.disassemble(seg.code, seg.procedure(1)) if i.mnemonic == 'XJP')
        low, high, _, cases = xjp.operands
        self.assertEqual((low, high, len(cases)), (-5, -1, 5))

    def test_native_procedures(self):
        natives = [p.number for p in self.code.segment(1).procedures if p.native]
        self.assertEqual(natives, list(range(26, 33)))
        random = self.code.segment(1).procedure(28)
        first = next(m6502.disassemble(self.code.segment(1).code, random))
        self.assertEqual(first[2], 'PLA')

    def test_listing_matches(self):
        for codefile, listing in [('WIZARDRY.CODE', 'WizardryCode/Wiz1WizardryPascal.txt'),
                                  ('SYSTEM.STARTUP', 'SystemStartup/Wiz1StartupPascal.txt')]:
            with self.subTest(codefile), redirect_stdout(io.StringIO()) as out:
                status = main(['check-listing', str(BOOT), str(EWERS / listing), codefile])
            self.assertEqual(status, 0, out.getvalue())
            self.assertIn(' 0 mismatches', out.getvalue())


class ScenarioTests(unittest.TestCase):
    def test_toc_and_rosters(self):
        import wizardry_scenario as ws
        played = ws.Scenario(IMAGES / 'wizardry_i_scenario.dsk')
        clean = ws.Scenario(IMAGES / 'snafaru_restored_scenario.dsk')
        self.assertEqual(played.name, 'PROVING GROUNDS OF THE MAD OVERLORD!')
        self.assertEqual(played.classes[-1], 'NINJA')
        self.assertEqual(played.on_disk['ZMAZE'], 10)
        self.assertEqual(next(played.roster())[1], 'JIB')
        self.assertEqual(next(clean.roster())[1], 'ABCDEFGHIJKLMN1')
        differing = {played.locate(i) for i in range(len(played.data)) if played.data[i] != clean.data[i]}
        self.assertEqual({k for k, _ in differing}, {'ZMAZE', 'ZOBJECT', 'ZCHAR'})


if __name__ == '__main__':
    unittest.main()
