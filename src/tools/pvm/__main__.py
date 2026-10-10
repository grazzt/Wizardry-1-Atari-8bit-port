"""Run WIZARDRY.CODE on the host p-machine.

    python3 -m pvm [--keys TEXT] [--seed N] [--max N] [--png FILE] [--trace FILE]

Keys use Python escapes: '\\r' is RETURN. The run stops when the program
ends, the keys run out, or --max instructions have executed; it then prints
the text screen and memory statistics. Run from the tools/ directory.
"""
import argparse
import codecs
from pathlib import Path
import re
import sys

from ucsd.codefile import CodeFile
from ucsd.disk import PascalDisk
from .console import Console, render_hires
from .machine import DiskUnit, PMachine, VMError

PROJECT = Path(__file__).resolve().parents[2]
IMAGES = PROJECT / 'appleII/images/wizardry_i'
LISTING = PROJECT / 'appleII/source/ewers_wizardry_i/WizardryCode/Wiz1WizardryPascal.txt'


def procedure_names(listing=LISTING):
    """(segment, procedure) -> name, from the declarations in Ewers's listing."""
    names = {}
    if not listing.exists():
        return names
    pattern = re.compile(r'^\s*\d+\s+(\d+)\s+(\d+):D\s+\d+\s+(?:SEGMENT\s+)?(?:PROCEDURE|FUNCTION)\s+(\w+)')
    for line in listing.read_text(encoding='latin1').splitlines():
        m = pattern.match(line)
        if m:
            names.setdefault((int(m.group(1)), int(m.group(2))), m.group(3))
    return names


def build(args, trace=None):
    boot = PascalDisk.open(args.boot)
    scenario = PascalDisk.open(args.scenario)
    keys = codecs.decode(args.keys, 'unicode_escape')
    startup = CodeFile(boot.read('SYSTEM.STARTUP')) if args.title else None
    return PMachine(CodeFile(boot.read('WIZARDRY.CODE')), {4: DiskUnit(scenario), 5: DiskUnit(boot)},
                    Console(keys), key_seed=args.seed, names=procedure_names(), trace=trace,
                    startup=startup)


def report(vm, outcome):
    print(vm.console.text(), end='')
    print('-' * 40)
    print(f'stopped: {outcome}; {vm.instructions:,} p-code instructions, {vm.native_calls:,} native calls, '
          f'{vm.cpu.cycles:,} 6502 instructions; keys used {vm.console.keys_read}')
    print(f'display: {"graphics" if vm.display["graphics"] else "text"}; '
          f'segments now loaded: {", ".join(s.name for s in vm.loaded.values())}')
    print(f'memory: stack top ${vm.stack_top:04X}, low-water ${vm.low_water:04X} '
          f'(peak stack {vm.stack_top - vm.low_water} bytes), heap high ${vm.heap_high:04X}, '
          f'least free {vm.low_water - vm.heap_high} bytes')


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python3 -m pvm', description=__doc__.split('\n')[0])
    parser.add_argument('--boot', default=IMAGES / 'wizardry_i_boot.dsk')
    parser.add_argument('--scenario', default=IMAGES / 'snafaru_restored_scenario.dsk')
    parser.add_argument('--keys', default='', help="scripted key presses, e.g. '\\r'")
    parser.add_argument('--seed', type=int, default=1, help='seed for key timing (the game RNG)')
    parser.add_argument('--title', action='store_true',
                        help='start with SYSTEM.STARTUP: title animation and options, then chain to the game')
    parser.add_argument('--max', type=int, default=20_000_000, help='instruction limit')
    parser.add_argument('--png', help='write the hi-res page as a PNG')
    parser.add_argument('--trace', help='write procedure calls to this file')
    parser.add_argument('--save-scenario', help='write the scenario disk, with any saves, to this file')
    args = parser.parse_args(argv)

    trace_file = open(args.trace, 'w') if args.trace else None
    vm = build(args, trace=(lambda line: trace_file.write(line + '\n')) if trace_file else None)
    try:
        outcome = vm.run(args.max)
    except VMError as error:
        outcome = f'{error} in {vm.name(vm.seg.number, vm.frame.proc.number)} at +{vm.ipc:#06x}'
    finally:
        if trace_file:
            trace_file.close()
    report(vm, outcome)
    if args.png:
        Path(args.png).write_bytes(render_hires(vm.mem))
    if args.save_scenario:
        Path(args.save_scenario).write_bytes(vm.units[4].image)
    return 0 if not outcome.startswith('execution error') else 1


if __name__ == '__main__':
    sys.exit(main())
