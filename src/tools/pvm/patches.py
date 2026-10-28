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
    'WIZARDRY.CODE': [
        (9, 16, 0, bytes([199, 0x79, 0x04, 0, 10, 191, 185, 0xFC])),
        # REWARDS.27 (CALCULAT): RANDOM MOD AVEAMT divides by zero for the fixed item drops
        # (reward records 20 and 21 have RANGE = 0; Werdna's Amulet is record 20). A fixed
        # drop is MININDX itself, so CALCULAT returns 0 when AVEAMT <= 0 and only rolls while
        # TRIES * AVEAMT > 0. TOTAL now lives on the evaluation stack (the original also held
        # it there around the RANDOM call), which pays for the guard:
        #   SLDL3 ; SLDL4 ; SLDC 0 ; GRTI ; MPI      TOTAL := MINADD * (AVEAMT > 0)
        #   loop: SLDL5 ; SLDL4 ; MPI ; SLDC 0 ; GRTI ; FJP done
        #   SLDC 0 ; SLDC 0 ; CXP 1,28 ; SLDL4 ; MODI ; ADI ; SLDC 1 ; ADI
        #   SLDL5 ; SLDC 1 ; SBI ; STL 5 ; UJP loop
        #   done: STL 1 (falls into the unchanged RNP 1)
        (19, 27, 0, bytes([
            0xDA, 0xDB, 0x00, 0xC5, 0x8F,
            0xDC, 0xDB, 0x8F, 0x00, 0xC5, 0xA1, 0x11,
            0x00, 0x00, 0xCD, 0x01, 0x1C, 0xDB, 0x8E, 0x82, 0x01, 0x82,
            0xDC, 0x01, 0x95, 0xCC, 0x05, 0xB9, 0xF6,
            0xCC, 0x01])),
        # ... and its jump-table entry -10 (the loop head) moves from offset 3 to offset 5:
        # an entry holds its own address minus the target address.
        (19, 27, 34, bytes([0x1D, 0x00])),
    ],
    # WIZBOOT.4 (CHKCOPY): keep reading the serial number (shown on the options
    # screen), then skip the disk-timing loop: UJP to the exit code.
    'SYSTEM.STARTUP': [(1, 4, 20, bytes([185, 0xFC]))],
}


def patch_segment_code(code, proc, offset, patch):
    """Return segment code with `patch` at proc.enter + offset; check the result.

    A patch in the procedure's code must end on an instruction boundary and jump to, or run
    into, EXITIC. A patch after the exit code rewrites jump-table words, each of which must
    still point into the procedure's code."""
    at = proc.enter + offset
    code = code[:at] + patch + code[at + len(patch):]
    if at > proc.exit:
        assert len(patch) % 2 == 0 and at % 2 == proc.jtab % 2, 'jump-table patches are whole words'
        for entry in range(at, at + len(patch), 2):
            target = entry - int.from_bytes(code[entry:entry + 2], 'little')
            assert proc.enter <= target <= proc.exit, 'jump-table entry must point into the procedure'
        return code
    pc, ins = at, None
    while pc < at + len(patch):
        ins = pcode.decode(code, pc, proc.jtab)
        pc = ins.end
    assert pc == at + len(patch), 'patch must end on an instruction boundary'
    assert (ins.mnemonic == 'UJP' and ins.targets[0] == proc.exit) or pc == proc.exit, \
        'patch must end by jumping to, or running into, EXITIC'
    return code


def apply(codefile, name):
    """Patch a CodeFile in place (its segments' code)."""
    for seg_number, proc_number, offset, patch in PATCHES.get(name, []):
        seg = codefile.segment(seg_number)
        seg.code = patch_segment_code(seg.code, seg.procedure(proc_number), offset, patch)
    return codefile
