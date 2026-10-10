"""Inspect Apple Pascal disk images and code files.

    python3 -m ucsd catalog IMAGE
    python3 -m ucsd extract IMAGE NAME [-o OUT] [--text]
    python3 -m ucsd segments IMAGE [CODEFILE]
    python3 -m ucsd disasm IMAGE [CODEFILE] [--segment S] [--proc N]
    python3 -m ucsd natives IMAGE [CODEFILE]
    python3 -m ucsd check-listing IMAGE LISTING [CODEFILE]

Run from the tools/ directory, or put tools/ on PYTHONPATH. CODEFILE defaults
to WIZARDRY.CODE.
"""
import argparse
from collections import Counter, defaultdict
from pathlib import Path
import re
import sys

from .codefile import CodeFile
from .disk import PascalDisk, decode_text
from . import m6502, pcode


def load_code(args):
    disk = PascalDisk.open(args.image)
    return CodeFile(disk.read(args.codefile))


def cmd_catalog(args):
    disk = PascalDisk.open(args.image)
    print(f'Volume {disk.volume}: ({disk.order} sector order), {len(disk.entries)} files')
    for e in disk.entries:
        print(f'  {e.name:16} {e.kind:5} {e.size:7}  blocks {e.first_block:3}-{e.next_block - 1:3}  {e.modified or ""}')


def cmd_extract(args):
    data = PascalDisk.open(args.image).read(args.name)
    out = Path(args.output or args.name)
    if args.text:
        out.write_text(decode_text(data))
    else:
        out.write_bytes(data)
    print(f'{out}: {out.stat().st_size} bytes')


def cmd_segments(args):
    cf = load_code(args)
    total = 0
    print('slot seg# name      kind    mtype  bytes  procs native  largest-locals')
    for s in cf.segments:
        native = sum(p.native for p in s.procedures)
        locals_ = max((p.data_bytes + p.param_bytes for p in s.procedures if not p.native), default=0)
        print(f'{s.index:4} {s.number:4} {s.name:9} {s.kind:7} {s.mtype:5} {s.length:6} '
              f'{len(s.procedures):5} {native:6}  {locals_:6}')
        total += s.length
    resident = cf.segments[0].length
    overlay = max((s for s in cf.segments[1:]), key=lambda s: s.length)
    print(f'\ntotal {total} bytes; resident {cf.segments[0].name} {resident}; '
          f'largest overlay {overlay.name} {overlay.length}; resident + largest = {resident + overlay.length}')


def print_pcode(seg, proc):
    print(f'\n; {seg.name} (segment {seg.number}) procedure {proc.number}: lex level {proc.lex_level}, '
          f'params {proc.param_bytes} bytes, locals {proc.data_bytes} bytes, '
          f'enter {proc.enter:#06x}, exit {proc.exit:#06x}')
    for ins in pcode.disassemble(seg.code, proc):
        mark = '>' if ins.offset == proc.exit else ' '
        print(f'{ins.offset - proc.enter:5}{mark} {ins.mnemonic:6} {ins.text}')


def print_native(seg, proc):
    _, relocs = m6502.native_layout(seg.code, proc)
    print(f'\n; {seg.name} (segment {seg.number}) procedure {proc.number}: native 6502, '
          f'relocations {[len(r) for r in relocs]} (base, segment, procedure, interpreter)')
    for offset, raw, text in m6502.disassemble(seg.code, proc):
        print(f'{offset:04X}  {raw.hex(" "):9} {text}')


def cmd_disasm(args):
    cf = load_code(args)
    segments = [cf.segment(int(args.segment) if args.segment.isdigit() else args.segment)] \
        if args.segment else cf.segments
    for seg in segments:
        procs = [seg.procedure(args.proc)] if args.proc else seg.procedures
        for proc in procs:
            (print_native if proc.native else print_pcode)(seg, proc)


def cmd_natives(args):
    """Inventory everything that leaves portable p-code."""
    cf = load_code(args)
    names = {s.number: s.name for s in cf.segments}
    print('Native 6502 procedures. Absolute operands are machine-specific addresses;')
    print('relocated operands point inside the code file and move with it.')
    for seg in cf.segments:
        for proc in seg.procedures:
            if not proc.native:
                continue
            end, relocs = m6502.native_layout(seg.code, proc)
            relocated = {r - proc.enter for lst in relocs for r in lst}
            absolute = set()
            for offset, raw, text in m6502.disassemble(seg.code, proc):
                if len(raw) == 3 and offset + 1 not in relocated:
                    absolute.add(f'${raw[1] | raw[2] << 8:04X}')
                elif len(raw) == 2 and ' $' in text and 'rel' not in text and not text.startswith('B'):
                    absolute.add(f'zp ${raw[1]:02X}' if '#' not in text else '')
            absolute.discard('')
            print(f'  {seg.name}.{proc.number:<3} {end - proc.enter:4} bytes, {len(relocated):2} relocated; '
                  f'absolute: {" ".join(sorted(absolute))}')
    csp, calls = Counter(), Counter()
    for seg in cf.segments:
        for proc in seg.procedures:
            if proc.native:
                continue
            for ins in pcode.disassemble(seg.code, proc):
                if ins.mnemonic == 'CSP':
                    csp[ins.text] += 1
                elif ins.mnemonic == 'CXP':
                    target_seg, target_proc = ins.operands
                    if target_seg == 0:
                        name = pcode.PASCALSY_PROCS.get(target_proc, f'proc {target_proc}')
                        calls[f'PASCALSY (OS).{target_proc} {name}'] += 1
                    elif target_seg in pcode.LIBRARY_UNITS and target_seg not in {s.number for s in cf.segments}:
                        calls[f'{pcode.LIBRARY_UNITS[target_seg]} (SYSTEM.LIBRARY).{target_proc}'] += 1
                    elif target_seg != seg.number:
                        callee = cf.segment(target_seg)
                        native = any(p.native and p.number == target_proc for p in callee.procedures)
                        calls[f'{callee.name}.{target_proc}{" (native)" if native else ""}'] += 1
    print('\nStandard procedures (CSP) used:')
    for name, n in csp.most_common():
        print(f'  {name:12} {n}')
    print('\nCalls outside the calling segment (CXP), most frequent first:')
    for name, n in calls.most_common():
        print(f'  {name:40} {n}')


LISTING_LINE = re.compile(r'^\s*\d+\s+(\d+)\s+(\d+):(D|\d+)\s+(\d+)')


def cmd_check_listing(args):
    """Every code line's IC must be an instruction boundary; the last IC of
    each procedure must equal its code size (JTAB + 2 - ENTERIC). The main
    program body is the exception: the compiler prints nothing after `END.`,
    so its final size is not in the listing."""
    cf = load_code(args)
    ics = defaultdict(set)
    program_body = set()
    for line in Path(args.listing).read_text(encoding='latin1').splitlines():
        m = LISTING_LINE.match(line)
        if m and m.group(3) != 'D':
            key = int(m.group(1)), int(m.group(2))
            ics[key].add(int(m.group(4)))
            if re.search(r'\bEND\.', line[m.end():]):
                program_body.add(key)
    checked = bad = 0
    for (segnum, procnum), offsets in sorted(ics.items()):
        seg = cf.segment(segnum)
        proc = seg.procedure(procnum)
        if proc.native:
            continue
        boundaries = {ins.offset - proc.enter for ins in pcode.disassemble(seg.code, proc)}
        size = proc.jtab + 2 - proc.enter
        for ic in sorted(offsets):
            checked += 1
            if ic not in boundaries and ic != size:
                bad += 1
                print(f'  {seg.name}.{procnum}: IC {ic} is not an instruction boundary')
        if max(offsets) != size and (segnum, procnum) not in program_body:
            bad += 1
            print(f'  {seg.name}.{procnum}: listing ends at {max(offsets)}, code size is {size}')
    procs = sum(1 for s in cf.segments for p in s.procedures if not p.native)
    print(f'{len(ics)} listed procedures ({procs} p-code procedures in file), '
          f'{checked} statement offsets checked, {bad} mismatches')
    return 1 if bad else 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python3 -m ucsd', description=__doc__.split('\n')[0])
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('catalog'); p.add_argument('image'); p.set_defaults(fn=cmd_catalog)
    p = sub.add_parser('extract'); p.add_argument('image'); p.add_argument('name')
    p.add_argument('-o', '--output'); p.add_argument('--text', action='store_true', help='decode a .TEXT file')
    p.set_defaults(fn=cmd_extract)
    for name, fn in [('segments', cmd_segments), ('natives', cmd_natives)]:
        p = sub.add_parser(name); p.add_argument('image'); p.add_argument('codefile', nargs='?', default='WIZARDRY.CODE')
        p.set_defaults(fn=fn)
    p = sub.add_parser('disasm'); p.add_argument('image'); p.add_argument('codefile', nargs='?', default='WIZARDRY.CODE')
    p.add_argument('--segment'); p.add_argument('--proc', type=int); p.set_defaults(fn=cmd_disasm)
    p = sub.add_parser('check-listing'); p.add_argument('image'); p.add_argument('listing')
    p.add_argument('codefile', nargs='?', default='WIZARDRY.CODE'); p.set_defaults(fn=cmd_check_listing)
    args = parser.parse_args(argv)
    return args.fn(args) or 0


if __name__ == '__main__':
    sys.exit(main())
