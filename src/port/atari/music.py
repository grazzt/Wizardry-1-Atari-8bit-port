"""NES music (an NSF's own player, run by tools/nes/nsf.py) as Atari POKEY data.

The NES song is replayed frame by frame and each frame's APU state mapped to
POKEY registers: the triangle (bass, down to 55 Hz) on channels 1+2 joined as
16 bits at 1.79 MHz, the two pulse voices on channels 3 and 4 (8 bits at
64 kHz, within a few cents mostly). Volumes carry over directly (both 0-15);
pulse duty and the triangle's shape cannot.

The register streams are stored as a two-level dictionary: each stream (a
voice's frequency or volume) is cut into blocks of B frames, consecutive
blocks into patterns of K blocks, and an order list gives the pattern for
every B*K frames. Repeated sections cost only order-list bytes. Tables are
column-major so each column fits an 8-bit index.

build.py calls music_images() and cue_include() (src/music_cues.inc).
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools/nes'))

from nsf import NSF, find_loop                              # noqa: E402

NES_CPU = 1789773
F179 = 1789790                      # POKEY 1.79 MHz clock (NTSC)
F64 = F179 / 28                     # POKEY 64 kHz clock
BASS_VOLUME = 10                    # the triangle has no volume control
PURE = 0xA0                         # AUDC distortion: pure tone
AUDCTL = 0x50                       # channel 1 at 1.79 MHz, channels 1+2 joined
B, K = 6, 8                         # frames per block, blocks per pattern

# Streams: name, POKEY register offsets (AUDF1=0, AUDC1=1, ... AUDC4=7)
STREAMS = [('bass_f', (0, 2)), ('bass_v', (3,)), ('lead_f', (4,)), ('lead_v', (5,)),
           ('harm_f', (6,)), ('harm_v', (7,))]


def pokey_frame(apu):
    """POKEY values per stream for one frame of NES APU registers."""
    out = {}
    t = apu[0x0A] | (apu[0x0B] & 7) << 8
    if apu[0x08] & 0x7F and t >= 2:
        n = round(F179 / (2 * NES_CPU / (32 * (t + 1))) - 7)
        out['bass_f'], out['bass_v'] = (n & 0xFF, n >> 8), (PURE | BASS_VOLUME,)
    else:
        out['bass_f'], out['bass_v'] = (0, 0), (PURE,)
    for name, ch in (('lead', 0), ('harm', 1)):
        vol = apu[4 * ch] & 0x0F if apu[4 * ch] & 0x10 else 0
        t = apu[4 * ch + 2] | (apu[4 * ch + 3] & 7) << 8
        if vol and t >= 8:
            n = max(0, min(255, round(F64 / (2 * NES_CPU / (16 * (t + 1))) - 1)))
            out[name + '_f'], out[name + '_v'] = (n,), (PURE | vol,)
        else:
            out[name + '_f'], out[name + '_v'] = (0,), (PURE,)
    return out


def song_frames(nsf_path, song, seconds, gap=2.0):
    """POKEY frames of a song, then `gap` seconds of silence before it repeats."""
    nsf = NSF(Path(nsf_path).read_bytes())
    frames = [pokey_frame(apu) for apu, _ in nsf.frames(song, round(seconds * 60))]
    silent = pokey_frame(bytes(0x18))
    frames += [silent] * round(gap * 60)
    while len(frames) % (B * K):
        frames.append(silent)
    return frames


def encode(frames):
    """Per stream: order list, pattern columns (K) and block columns (B per register)."""
    if len(frames) // (B * K) > 256:
        raise ValueError('song too long for an 8-bit order list')
    out = {}
    for name, regs in STREAMS:
        values = [f[name] for f in frames]
        blocks = [tuple(values[i:i + B]) for i in range(0, len(values), B)]
        block_ids = {}
        for b in blocks:
            block_ids.setdefault(b, len(block_ids))
        order_blocks = [block_ids[b] for b in blocks]
        patterns = [tuple(order_blocks[i:i + K]) for i in range(0, len(order_blocks), K)]
        pattern_ids = {}
        for p in patterns:
            pattern_ids.setdefault(p, len(pattern_ids))
        if len(block_ids) > 256 or len(pattern_ids) > 256:
            raise ValueError(f'{name}: too many blocks or patterns')
        unique_blocks = list(block_ids)
        unique_patterns = list(pattern_ids)
        out[name] = {
            'order': [pattern_ids[p] for p in patterns],
            'patcols': [[p[k] for p in unique_patterns] for k in range(K)],
            'blkcols': [[[b[j][r] for b in unique_blocks] for j in range(B)] for r in range(len(regs))],
        }
    return out


def decode(enc, length):
    """Inverse of encode(), for checking: POKEY register lists per frame."""
    frames = []
    for f in range(length):
        j, k, p = f % B, (f // B) % K, f // (B * K)
        regs = [0] * 8
        for name, offsets in STREAMS:
            s = enc[name]
            block = s['patcols'][k][s['order'][p]]
            for r, off in enumerate(offsets):
                regs[off] = s['blkcols'][r][j][block]
        frames.append(regs)
    return frames


# --- song images -------------------------------------------------------------------
# A song image runs at a fixed address (its base): a header, then the tables.
#   +0 patterns N, +1 loop pattern (or $FF: stop at the end), then for each of
#   the 6 streams a 45-byte descriptor: register count, order-list address,
#   8 pattern-column addresses, and for each of 2 registers: POKEY register
#   offset and 6 block-column addresses.
HEADER = 2 + 6 * 45
NO_LOOP = 0xFF

# NSF song numbers (from the NSF's playlist): what plays where.
OPENING, CASTLE, TAVERN, BOLTAC, INN, TEMPLE, EDGE, DUNGEON, CAMP, FIGHT, WERDNA, \
    EXTERMINATED, COMPLETE, ITEM, ENCOUNTER, FANFARE, CHANT, LEVELUP = range(1, 19)
THEMES = range(CASTLE, COMPLETE + 1)        # loaded from disk as they are needed
JINGLES = range(ENCOUNTER, LEVELUP + 1)     # always in memory, played over a theme

# Game procedures (segment, procedure, calling segment, calling procedure or 0 for
# any) whose call starts a song. Numbers from the Ewers listing.
CUES = [
    (16, 1, 0, 0, CASTLE),          # CASTLE
    (16, 4, 16, 1, CASTLE),         # DSPTITLE from CASTLE: back on the castle menu
    (16, 6, 0, 0, TAVERN),          # GILGAMSH
    (16, 15, 0, 0, INN),            # ADVNTINN
    (16, 26, 0, 0, LEVELUP),        # MADELEV
    (8, 2, 0, 0, TEMPLE),           # CANT
    (8, 8, 0, 0, CHANT),            # DOCANT
    (8, 10, 0, 0, BOLTAC),          # BOLTAC
    (8, 21, 0, 0, EXTERMINATED),    # CEMETARY
    (8, 26, 0, 0, EDGE),            # EDGETOWN
    (8, 30, 0, 0, COMPLETE),        # CONGRATS
    (17, 1, 0, 0, EDGE),            # ROLLER: the training grounds
    (18, 31, 0, 0, CAMP),           # CAMPMEN2: camp in the maze
    (20, 13, 0, 0, ENCOUNTER),      # ENCOUNTR
    (20, 14, 0, 0, DUNGEON),        # RUNMAIN
    (20, 26, 0, 0, ENCOUNTER),      # CHENCOUN: a fixed encounter
    (10, 1, 0, 0, FIGHT),           # COMBAT
    (19, 31, 0, 0, FANFARE),        # GIVEEXP: "FOR KILLING THE MONSTERS"
]


def song_sequence(nsf, song):
    """POKEY frames of a song, padded to whole patterns, and its loop pattern."""
    silent = pokey_frame(bytes(0x18))
    states = [s for s, _ in nsf.frames(song, 200 * 60 if song in THEMES or song == OPENING else 600)]
    frames = [pokey_frame(s) for s in states]
    loop = find_loop(states) if song in THEMES and song != COMPLETE else None
    if loop:
        start, period = loop
        pre = (-start) % (B * K)            # silence first, so the loop starts a pattern
        seq, loop_pattern = [silent] * pre + frames[:start + period], (pre + start) // (B * K)
    else:
        def sounding(s):
            return any(s[4 * c] & 0x10 and s[4 * c] & 0x0F for c in (0, 1)) or s[8] & 0x7F
        last = max(i for i, s in enumerate(states) if sounding(s))
        seq, loop_pattern = frames[:last + 1], NO_LOOP
        if song == OPENING:                  # the title: again after a pause
            seq, loop_pattern = seq + [silent] * 120, 0
    while len(seq) % (B * K):
        seq.append(silent)
    return seq, loop_pattern


def song_image(frames, loop_pattern, base):
    """The song as bytes to be placed at address `base`."""
    enc = encode(frames)
    patterns = len(frames) // (B * K)
    assert patterns <= 255 and (loop_pattern == NO_LOOP or loop_pattern < patterns)
    header, data = bytearray([patterns, loop_pattern]), bytearray()

    def place(values):
        addr = base + HEADER + len(data)
        data.extend(values)
        return addr

    for name, offsets in STREAMS:
        s = enc[name]
        desc = bytearray([len(offsets)])
        desc += place(s['order']).to_bytes(2, 'little')
        for k in range(K):
            desc += place(s['patcols'][k]).to_bytes(2, 'little')
        for r in range(2):
            if r < len(offsets):
                desc.append(offsets[r])
                for j in range(B):
                    desc += place(s['blkcols'][r][j]).to_bytes(2, 'little')
            else:
                desc += bytes(13)
        assert len(desc) == 45
        header += desc
    return bytes(header + data)


def music_images(nsf_path, jingle_base, slot):
    """Images for the disk: jingles (all at jingle_base on), and each song for the slot."""
    nsf = NSF(Path(nsf_path).read_bytes())
    jingles, addresses = bytearray(), {}
    for song in JINGLES:
        addresses[song] = jingle_base + len(jingles)
        jingles += song_image(*song_sequence(nsf, song), addresses[song])
    songs = {song: song_image(*song_sequence(nsf, song), slot) for song in [OPENING, *THEMES]}
    return bytes(jingles), addresses, songs


def cue_include(addresses, song_sectors):
    """ca65 tables for the game overlay: cues by segment, the song directory."""
    by_seg = sorted(CUES)
    first = [0xFF] * 32
    for i, cue in enumerate(by_seg):
        if first[cue[0]] == 0xFF:
            first[cue[0]] = i
    lines = ['; Generated by build.py (port/atari/music.py): where each song plays.',
             'cue_first:  .byte ' + ', '.join(map(str, first))]
    for name, col in (('cue_seg', 0), ('cue_proc', 1), ('cue_fseg', 2), ('cue_fproc', 3), ('cue_song', 4)):
        lines.append(f'{name}: .byte ' + ', '.join(str(c[col]) for c in by_seg) + ', 0')
    songs = range(OPENING, LEVELUP + 1)
    lines.append('song_sec_lo: .byte ' + ', '.join(str(song_sectors.get(s, (0, 0))[0] & 0xFF) for s in songs))
    lines.append('song_sec_hi: .byte ' + ', '.join(str(song_sectors.get(s, (0, 0))[0] >> 8) for s in songs))
    lines.append('song_secs:   .byte ' + ', '.join(str(song_sectors.get(s, (0, 0))[1]) for s in songs))
    lines.append('song_jlo:    .byte ' + ', '.join(str(addresses.get(s, 0) & 0xFF) for s in songs))
    lines.append('song_jhi:    .byte ' + ', '.join(str(addresses.get(s, 0) >> 8) for s in songs))
    return '\n'.join(lines) + '\n'
