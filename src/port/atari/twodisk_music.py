"""Relocation and generated directory for compressed gameplay music on Disk 2."""
import struct
import music

PLAYER = 0xE600
JINGLES = 0xD800
SLOT = 0xE800


def relocate(image, old_base, new_base):
    """Relocate the existing player-format pointers without changing any frame."""
    result = bytearray(image)
    for stream in range(6):
        descriptor = 2 + 45 * stream
        count = image[descriptor]
        offsets = [1] + [3 + 2 * k for k in range(music.K)]
        offsets += [20 + 13 * r + 2 * j for r in range(count) for j in range(music.B)]
        for offset in offsets:
            at = descriptor + offset
            pointer = struct.unpack_from('<H', image, at)[0]
            if not old_base <= pointer < old_base + len(image):
                raise ValueError('music table pointer is outside its image')
            struct.pack_into('<H', result, at, pointer - old_base + new_base)
    if new_base + len(image) > 0xFFFA:
        raise ValueError('music image overlaps interrupt vectors')
    return bytes(result)


def relocate_images(images):
    jingles, addresses, songs = images
    relocated, new_addresses = bytearray(), {}
    for song in music.JINGLES:
        old = addresses[song]
        end = addresses.get(song + 1, 0xC200 + len(jingles))
        image = jingles[old - 0xC200:end - 0xC200]
        new_addresses[song] = JINGLES + len(relocated)
        relocated += relocate(image, old, new_addresses[song])
    if JINGLES + len(relocated) > PLAYER:
        raise ValueError('jingles overlap the music player')
    required = {cue[4] for cue in music.CUES}
    themes = {song: relocate(image, 0xD800, SLOT) for song, image in songs.items()
              if song in required}
    return bytes(relocated), new_addresses, themes


def records(images):
    jingles, addresses, themes = images
    result = [(song, SLOT, image) for song, image in sorted(themes.items())]
    for song in music.JINGLES:
        start = addresses[song]
        end = addresses.get(song + 1, JINGLES + len(jingles))
        result.append((song, start, jingles[start - JINGLES:end - JINGLES]))
    return result


def cue_include(images, directory):
    # Keep the existing cue and jingle-address tables, adding byte offsets and
    # decoded lengths for streams loaded by the shared decoder.
    entries = {entry['song']: entry for entry in directory}
    sectors = {song: (entry['sector'], 0) for song, entry in entries.items()}
    text = music.cue_include(images[1], sectors)
    for label, field, shift in (('song_cmp_ctl', 'control', 0),
                                ('song_len_lo', 'length', 0), ('song_len_hi', 'length', 8)):
        values = [(entries.get(song, {}).get(field, 0) >> shift) & 255 for song in range(1, 19)]
        text += f'{label}: .byte ' + ', '.join(map(str, values)) + '\n'
    return text
