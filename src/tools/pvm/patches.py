"""Code patches applied to the Apple code files, shared by pvm and the Atari build.

Both replace copy-protection checks that time raw disk nibbles, which neither
a host nor an Atari can reproduce. Each patch is (segment, procedure, offset
from the procedure's entry, bytes), and is checked against the code it
replaces when applied.
"""
from ucsd import pcode

PATCHES = {
    # SPECIALS.16 (COPYPROT): store the success marker (10 at $0479, tested by
    # CASTLE before "crash and burn"), then jump to the exit code:
    #   LDCI 1145 ; SLDC 0 ; SLDC 10 ; STB ; UJP via jump-table entry -4 (EXITIC)
    'WIZARDRY.CODE': [(9, 16, 0, bytes([199, 0x79, 0x04, 0, 10, 191, 185, 0xFC]))],
    # WIZBOOT.4 (CHKCOPY): keep reading the serial number (shown on the options
    # screen), then skip the disk-timing loop: UJP to the exit code.
    'SYSTEM.STARTUP': [(1, 4, 20, bytes([185, 0xFC]))],
}


def patch_segment_code(code, proc, offset, patch):
    """Return segment code with `patch` at proc.enter + offset; check the result."""
    at = proc.enter + offset
    code = code[:at] + patch + code[at + len(patch):]
    pc, ins = at, None
    while pc < at + len(patch):
        ins = pcode.decode(code, pc, proc.jtab)
        pc = ins.end
    assert pc == at + len(patch), 'patch must end on an instruction boundary'
    assert ins.mnemonic == 'UJP' and ins.targets[0] == proc.exit, 'patch must end by jumping to EXITIC'
    return code


def apply(codefile, name):
    """Patch a CodeFile in place (its segments' code)."""
    for seg_number, proc_number, offset, patch in PATCHES.get(name, []):
        seg = codefile.segment(seg_number)
        seg.code = patch_segment_code(seg.code, seg.procedure(proc_number), offset, patch)
    return codefile
