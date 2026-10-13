"""Drive Atari800 (libatari800) from Python: boot a disk, type keys, read memory.

Needs tools/emulators/local/lib/libatari800.so, built by
tools/emulators/setup.sh. The machine is a 65XE equivalent: 800XL with
64 KB, the bundled Altirra OS, BASIC disabled, NTSC.
"""
import ctypes
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
LIBRARY = PROJECT / 'tools/emulators/local/lib/libatari800.so'


class Input(ctypes.Structure):
    _fields_ = [(name, ctypes.c_ubyte) for name in (
        'keychar', 'keycode', 'special', 'shift', 'control', 'start', 'select', 'option',
        'joy0', 'trig0', 'joy1', 'trig1', 'joy2', 'trig2', 'joy3', 'trig3',
        'mousex', 'mousey', 'mouse_buttons', 'mouse_mode')]


class Atari:
    _instance = None    # libatari800 is a singleton; reuse the loaded library

    def __init__(self, disk, xex=None, extra_args=(), sound=False, sio_patch=None):
        if Atari._instance is None:
            Atari._lib = ctypes.CDLL(str(LIBRARY))
            Atari._lib.libatari800_get_main_memory_ptr.restype = ctypes.POINTER(ctypes.c_ubyte * 0x10000)
            Atari._lib.libatari800_error_message.restype = ctypes.c_char_p
            Atari._lib.libatari800_mount_disk.restype = ctypes.c_int
            Atari._lib.libatari800_set_sio_patch_enabled.restype = ctypes.c_int
        Atari._instance = self
        lib = self._lib
        args = ['atari800', '-config', str(Path(__file__).parent / 'build/harness.cfg'),
                '-xl', '-ntsc', '-nobasic', '-xl-rev', 'altirra',
                *([] if sound else ['-nosound']), *extra_args]
        args += [str(disk)]
        if xex:
            args += [str(xex)]
        argv = (ctypes.c_char_p * len(args))(*[a.encode() for a in args])
        if not lib.libatari800_init(len(args), argv):
            raise RuntimeError('libatari800_init failed')
        # libatari800 retains this global across init calls. Restore the
        # usual fast setting unless this instance explicitly requests real SIO.
        self.sio_patch(True if sio_patch is None else sio_patch)
        self.input = Input()
        self.frames = 0
        self.audio = bytearray() if sound else None
        self.on_frame = None        # called after every emulated frame (recording)

    @property
    def memory(self):
        return self._lib.libatari800_get_main_memory_ptr().contents

    def frame(self, count=1):
        for _ in range(count):
            self._lib.libatari800_next_frame(ctypes.byref(self.input))
            self.frames += 1
            if self.audio is not None:
                lib = self._lib
                lib.libatari800_get_sound_buffer.restype = ctypes.c_void_p
                n = lib.libatari800_get_sound_buffer_len()
                self.audio += ctypes.string_at(lib.libatari800_get_sound_buffer(), n)
            if self.on_frame:
                self.on_frame()

    def screen(self):
        """The emulated display: 384x240 bytes of Atari colour values."""
        self._lib.libatari800_get_screen_ptr.restype = ctypes.POINTER(ctypes.c_ubyte * (384 * 240))
        return bytes(self._lib.libatari800_get_screen_ptr().contents)

    def screenshot(self, path):
        """Write the emulated display (384x240) as a PNG, in Atari800's NTSC colours."""
        import struct, zlib
        self._lib.libatari800_get_screen_ptr.restype = ctypes.POINTER(ctypes.c_ubyte * (384 * 240))
        pixels = bytes(self._lib.libatari800_get_screen_ptr().contents)
        palette = self.palette()
        rows = [b''.join(palette[pixels[y * 384 + x]] for x in range(384)) for y in range(240)]
        raw = b''.join(b'\0' + r for r in rows)

        def chunk(kind, data):
            return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
        Path(path).write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 384, 240, 8, 2, 0, 0, 0))
                               + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))

    def save_audio(self, path):
        """Write the sound recorded since start (Atari(..., sound=True)) as a WAV file.
        libatari800 is loaded once per process: sound works only if the first
        Atari of the process was made with sound=True."""
        import wave
        lib = self._lib
        with wave.open(str(path), 'wb') as w:
            w.setnchannels(lib.libatari800_get_num_sound_channels())
            w.setsampwidth(lib.libatari800_get_sound_sample_size())
            w.setframerate(lib.libatari800_get_sound_frequency())
            w.writeframes(bytes(self.audio))

    def palette(self):
        """Atari800's own NTSC palette: 256 RGB triples, indexed by colour register value."""
        table = (ctypes.c_int * 256)()
        self._lib.COLOURS_NTSC_Update(table)
        return [bytes(((v >> 16) & 255, (v >> 8) & 255, v & 255)) for v in table]

    def cpu(self):
        """6502 registers: dict with PC, A, X, Y, S, P (from a state snapshot)."""
        import struct
        buf = ctypes.create_string_buffer(128 + 128 + 210000)
        self._lib.libatari800_get_current_state(buf)
        cpu_off, pc_off = struct.unpack_from('<II', buf.raw, 4)
        state = buf.raw[256:]
        a, p, s, x, y = state[cpu_off:cpu_off + 5]
        pc = struct.unpack_from('<H', state, pc_off)[0]
        return {'PC': pc, 'A': a, 'X': x, 'Y': y, 'S': s, 'P': p}

    def peek(self, addr):
        return self.memory[addr]

    def peekw(self, addr):
        return self.memory[addr] | self.memory[addr + 1] << 8

    def type(self, text, hold=3, gap=3):
        """Press and release each key ('\r' is RETURN, '\x1b' ESC)."""
        for ch in text:
            self.input.keychar = 10 if ch == '\r' else ord(ch)
            self.frame(hold)
            self.input.keychar = 0
            self.frame(gap)

    def mount_disk(self, path, read_only=False):
        """Swap the image in drive 1 at runtime (a real disk change)."""
        self._lib.libatari800_mount_disk(1, str(path).encode(), int(read_only))

    def sio_patch(self, enabled):
        """Fast disk access: the emulator's SIO patch, on or off."""
        self._lib.libatari800_set_sio_patch_enabled(int(enabled))

    def run_until(self, predicate, limit=3000, step=5):
        """Run frames until predicate(self) is true; return frames used or None."""
        start = self.frames
        while self.frames - start < limit:
            if predicate(self):
                return self.frames - start
            self.frame(step)
        return None

    def text_memory(self, addr=0xBC00):
        """The runtime's 40x24 text screen, whether or not it is displayed."""
        mem = self.memory
        rows = [''.join(_internal_to_ascii(mem[addr + 40 * r + c]) for c in range(40)).rstrip()
                for r in range(24)]
        return '\n'.join(rows).rstrip('\n') + '\n'

    def text_screen(self):
        """Decode an ANTIC mode 2 (40-column text) screen via the display list."""
        mem = self.memory
        dl = self.peekw(0x230)
        rows, addr, pc = [], None, dl
        for _ in range(200):
            ins = mem[pc]
            mode = ins & 0x0F
            if ins == 0x41 or ins & 0x0F == 0x01:            # JVB / JMP
                break
            if mode == 0:
                pc += 1
                continue
            if ins & 0x40:
                addr = mem[pc + 1] | mem[pc + 2] << 8
                pc += 3
            else:
                pc += 1
            if mode == 2:
                rows.append(''.join(_internal_to_ascii(mem[addr + i]) for i in range(40)).rstrip())
                addr += 40
            else:
                return None                                    # not a text screen
        return '\n'.join(rows).rstrip('\n') + '\n'


def _internal_to_ascii(code):
    code &= 0x7F
    if code < 0x40:
        return chr(code + 0x20)
    if code < 0x60:
        return "?"
    return chr(code)
