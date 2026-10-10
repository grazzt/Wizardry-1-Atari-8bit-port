"""Run an NSF (NES Sound Format) file's own player and record the NES APU.

    python3 tools/nes/nsf.py FILE.nsf [--song N] [--seconds S]

The play routine is called once per NTSC frame (60 Hz), as on the NES. After
each call the APU registers ($4000-$4017) are captured, giving a frame-by-frame
register stream that a converter can turn into Atari POKEY data.
"""
import argparse
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pvm.cpu6502 import CPU6502                         # noqa: E402

RETURN = 0xFFF0                     # a stop address the player never reaches


class NESCPU(CPU6502):
    """6502 with flat NES memory: writes to $4000-$4017 go to the APU log."""

    def __init__(self, memory):
        super().__init__(memory)
        self.apu = bytearray(0x18)
        self.writes = []

    def read(self, addr):
        if addr == 0x4015:
            return 0x1F
        return self.m[addr]

    def write(self, addr, value):
        value &= 0xFF
        if 0x4000 <= addr <= 0x4017:
            self.apu[addr - 0x4000] = value
            self.writes.append((addr, value))
        elif addr < 0x8000:
            self.m[addr] = value


class NSF:
    def __init__(self, data):
        if data[:5] != b'NESM\x1a':
            raise ValueError('not an NSF file')
        (self.version, self.songs, self.start, self.load, self.init,
         self.play) = struct.unpack_from('<BBBHHH', data, 5)
        self.name, self.artist, self.copyright = (
            data[o:o + 32].split(b'\0')[0].decode('latin-1') for o in (0x0E, 0x2E, 0x4E))
        self.ntsc_speed = struct.unpack_from('<H', data, 0x6E)[0]
        self.banks = data[0x70:0x78]
        if any(self.banks):
            raise NotImplementedError('bank-switched NSF')
        self.code = data[0x80:]

    def machine(self, song):
        """A CPU with the song initialised (song numbers start at 1)."""
        mem = bytearray(0x10000)
        mem[self.load:self.load + len(self.code)] = self.code
        cpu = NESCPU(mem)
        for reg in range(0x4000, 0x4014):
            cpu.write(reg, 0)
        cpu.write(0x4015, 0x0F)
        cpu.write(0x4017, 0x40)
        self.call(cpu, self.init, a=song - 1, x=0)
        cpu.writes.clear()
        return cpu

    @staticmethod
    def call(cpu, addr, a=0, x=0):
        cpu.a, cpu.x, cpu.y, cpu.s = a, x, 0, 0xFF
        cpu.push((RETURN - 1) >> 8)
        cpu.push((RETURN - 1) & 0xFF)
        cpu.run(addr, RETURN, limit=2_000_000)

    def frames(self, song, count):
        """APU register state after each of `count` play calls, and each frame's writes."""
        cpu = self.machine(song)
        for _ in range(count):
            cpu.writes = []
            self.call(cpu, self.play)
            yield bytes(cpu.apu), cpu.writes


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('file')
    parser.add_argument('--song', type=int)
    parser.add_argument('--seconds', type=float, default=200)
    args = parser.parse_args()
    nsf = NSF(Path(args.file).read_bytes())
    print(f'{nsf.name} / {nsf.artist} / {nsf.copyright}: {nsf.songs} songs, load ${nsf.load:04X}, '
          f'init ${nsf.init:04X}, play ${nsf.play:04X}')
    songs = [args.song] if args.song else range(1, nsf.songs + 1)
    for song in songs:
        n = int(args.seconds * 60)
        states = [s for s, _ in nsf.frames(song, n)]
        print(f'song {song:2}: {describe(states)}')


def describe(states):
    """Sounding length, and the loop if the register stream repeats."""
    def sounding(s):
        return any(s[4 * ch] & 0x0F for ch in (0, 1, 3)) or s[8] & 0x7F
    last = max((i for i, s in enumerate(states) if sounding(s)), default=-1)
    loop = find_loop(states)
    text = f'sound until {(last + 1) / 60:6.1f} s'
    if loop:
        start, period = loop
        text += f', loops every {period / 60:.1f} s from {start / 60:.1f} s'
    elif last + 1 < len(states):
        text += ', then silent'
    return text


def find_loop(states, min_period=120):
    """(start, period) of the shortest repetition that holds to the end, or None."""
    n = len(states)
    tail = states[n // 2:]
    for period in range(min_period, n // 2):
        if all(states[i] == states[i - period] for i in range(n // 2, n)):
            start = n // 2
            while start - period > 0 and states[start - 1] == states[start - 1 - period]:
                start -= 1
            return start - period, period
    return None if tail else None


if __name__ == '__main__':
    main()
