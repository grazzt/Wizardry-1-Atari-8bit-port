"""Seed optional powerful characters in the original 208-byte TCHAR format.

Offsets and packed fields are checked against the original game's p-code
(UTILITIE, ROLLER and CASTLE), alongside Ewers's TCHAR listing. Only vacant
roster records change; existing characters and the scenario remain intact.
"""
import struct

from ucsd.disk import PascalDisk
from wizardry_scenario import RECORD_SIZE, Scenario

MEMBERS = (('VANGUARD', 'LORD'), ('RONIN', 'SAMURAI'), ('SHADOW', 'THIEF'),
           ('DAWN', 'PRIEST'), ('SAGE', 'BISHOP'), ('MERLIN', 'MAGE'))
LEVEL = 50
HIT_POINTS = 999
GOLD = 1_000_000
EXPERIENCE = 50_000_000
CASTS = 9
LOST = 7                         # the game treats LOST records as vacant


def character(name, class_index):
    record = bytearray(RECORD_SIZE['ZCHAR'])
    encoded = name.encode('ascii')
    if not 1 <= len(encoded) <= 15:
        raise ValueError('party character names must be 1..15 ASCII characters')
    record[0] = len(encoded)
    record[1:1 + len(encoded)] = encoded
    # Empty password; in town, human, age 18, OK, good alignment.
    struct.pack_into('<6h', record, 32, 0, 1, class_index, 18 * 52, 0, 1)
    # UCSD packs three 5-bit attributes per 16-bit word, without crossing it.
    attributes = 18 | (18 << 5) | (18 << 10)
    struct.pack_into('<HHHH', record, 44, attributes, attributes,
                     1 | (1 << 5) | (1 << 10), 1 | (1 << 5))
    # TWIZLONG is three base-10,000 digits, least significant word first.
    for offset, value in ((52, GOLD), (124, EXPERIENCE)):
        struct.pack_into('<3H', record, offset, value % 10_000,
                         value // 10_000 % 10_000, value // 100_000_000)
    # POSS at 58 stays empty. MAXLEVAC, CHARLEV, HPLEFT, HPMAX follow EXP.
    struct.pack_into('<4h', record, 130, LEVEL, LEVEL, HIT_POINTS, HIT_POINTS)
    # The actual spell books use indexes 1..50; bit 0 is unused. The compiled
    # game allocates four words, including room for the final KADORTO bit.
    record[138:146] = ((1 << 51) - 2).to_bytes(8, 'little')
    struct.pack_into('<14h', record, 146, *([CASTS] * 14))
    struct.pack_into('<h', record, 176, 10)  # unarmored AC; EQUIPCHR recalculates
    return bytes(record)


def seed(disk):
    """Return a new PascalDisk and member metadata, or fail before any write.

    Preserve occupied slots. Reuse the game's LOST/deleted placeholders and
    empty names. If a member name already exists, pick a unique suffix.
    """
    scenario = Scenario(disk)
    roster = list(scenario.roster())
    slots = [index for index, name, _, _, _, _, status, _ in roster
             if status == LOST or not name]
    if len(slots) < len(MEMBERS):
        raise SystemExit('--party needs six vacant roster slots; this scenario has '
                         f'{len(slots)} (use a fresh scenario or delete characters first)')
    names = {name for _, name, _, _, _, _, status, _ in roster if name and status != LOST}
    volume = bytearray(b''.join(disk.block(block) for block in range(280)))
    entry = disk.entry('SCENARIO.DATA')
    members = []
    for slot, (base, cls) in zip(slots, MEMBERS):
        name, suffix = base, 2
        while name in names:
            name = f'{base}{suffix}'
            suffix += 1
        names.add(name)
        record = character(name, scenario.classes.index(cls))
        offset = entry.first_block * 512 + scenario.record_offset('ZCHAR', slot)
        volume[offset:offset + len(record)] = record
        members.append({'name': name, 'class': cls, 'slot': slot,
                        'level': LEVEL, 'hp': HIT_POINTS, 'gold': GOLD})
    # A block-order volume is a valid ProDOS-order image; PascalDisk detects it.
    return PascalDisk(bytes(volume), f'{disk.name} + OP party'), members


def tables_include(disk, members):
    """Address and identity tables for automatic formation from saved records."""
    scenario = Scenario(disk)
    first = disk.entry('SCENARIO.DATA').first_block
    blocks, offsets, names = [], [], []
    for member in members:
        cache, index = divmod(member['slot'], scenario.per_cache['ZCHAR'])
        blocks.append(first + scenario.first_block['ZCHAR'] + cache * 2)
        offsets.append(index * RECORD_SIZE['ZCHAR'])
        encoded = member['name'].encode('ascii')
        names.extend((bytes([len(encoded)]) + encoded).ljust(16, b'\0'))
    text = '; Generated party roster locations; read live saves at startup.\n'
    for label, values in (('party_slots', [m['slot'] for m in members]),
                          ('party_block_lo', [b & 255 for b in blocks]),
                          ('party_block_hi', [b >> 8 for b in blocks]),
                          ('party_offset_lo', [o & 255 for o in offsets]),
                          ('party_offset_hi', [o >> 8 for o in offsets]),
                          ('party_names', names)):
        text += label + ': .byte ' + ', '.join(map(str, values)) + '\n'
    return text
