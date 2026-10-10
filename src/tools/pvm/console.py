"""Host console: Apple Pascal text screen, scripted keyboard, hi-res rendering."""
import struct
import zlib

WIDTH, HEIGHT = 40, 24


class InputExhausted(Exception):
    """The VM needs a key and the script has none left."""


class Console:
    """40x24 text screen driven by Apple Pascal console control codes.

    The cursor may sit beyond column 39 (Wizardry parks it at column 41 so
    that echoed keys stay invisible); characters written there are dropped.
    """

    def __init__(self, keys=''):
        self.rows = [[' '] * WIDTH for _ in range(HEIGHT)]
        self.x = self.y = 0
        self.keys = list(keys)
        self.keys_read = 0
        self.transcript = []          # every character written, for logs
        self.bells = 0

    # -- output -------------------------------------------------------------
    def write(self, text):
        for ch in text:
            self.put(ord(ch))

    def put(self, code):
        self.transcript.append(chr(code) if code >= 32 or code in (10, 13) else f'<{code}>')
        if code == 13:                  # CR: Apple Pascal BIOS also feeds a line
            self.x = 0
            self._down()
        elif code == 10:
            self._down()
        elif code == 12:                # FF: clear screen, home
            self.rows = [[' '] * WIDTH for _ in range(HEIGHT)]
            self.x = self.y = 0
        elif code == 11:                # VT: clear to end of screen
            self._clear_eol()
            for row in self.rows[self.y + 1:]:
                row[:] = [' '] * WIDTH
        elif code == 29:                # GS: clear to end of line
            self._clear_eol()
        elif code == 25:                # EM: home
            self.x = self.y = 0
        elif code == 8:
            self.x = max(0, self.x - 1)
        elif code == 28:
            self.x += 1
        elif code == 31:
            self.y = max(0, self.y - 1)
        elif code == 7:
            self.bells += 1
        elif code >= 32:
            if self.x < WIDTH and self.y < HEIGHT:
                self.rows[self.y][self.x] = chr(code & 0x7F)
            self.x += 1

    def _clear_eol(self):
        if self.y < HEIGHT and self.x < WIDTH:
            self.rows[self.y][self.x:] = [' '] * (WIDTH - self.x)

    def _down(self):
        if self.y < HEIGHT - 1:
            self.y += 1
        else:
            self.rows = self.rows[1:] + [[' '] * WIDTH]

    def goto(self, x, y):
        self.x = max(0, x)
        self.y = max(0, min(HEIGHT - 1, y))

    def text(self):
        return '\n'.join(''.join(r).rstrip() for r in self.rows).rstrip('\n') + '\n'

    # -- input --------------------------------------------------------------
    def key_available(self):
        return bool(self.keys)

    def read_key(self):
        if not self.keys:
            raise InputExhausted()
        self.keys_read += 1
        return ord(self.keys.pop(0))


def render_hires(memory, page=0x2000, scale=2):
    """Render an Apple II hi-res page as monochrome PNG bytes (280x192)."""
    rows = []
    for y in range(192):
        base = page + (y & 7) * 0x400 + ((y >> 3) & 7) * 0x80 + (y >> 6) * 0x28
        line = bytearray()
        for col in range(40):
            byte = memory[base + col]
            for bit in range(7):
                line.append(255 if byte >> bit & 1 else 0)
        line = bytes(v for v in line for _ in range(scale))
        rows.extend([line] * scale)
    return _png(280 * scale, 192 * scale, rows)


def _png(width, height, rows):
    raw = b''.join(b'\0' + bytes(r) for r in rows)

    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 0, 0, 0, 0)) +
            chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))
