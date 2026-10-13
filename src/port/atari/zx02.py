"""ZX02 host compression and a bounded reference decoder for WZC3 volumes."""
import hashlib
from pathlib import Path
import subprocess
import tempfile

SOURCE = Path(__file__).resolve().parents[2] / 'tools/zx02'
BUILD = Path(__file__).resolve().parent / 'build'
_COMPRESSOR = None
_CACHE = {}


def compressor():
    global _COMPRESSOR
    if _COMPRESSOR is None:
        inputs = sorted(SOURCE.glob('*.[ch]'))
        digest = hashlib.sha256(b''.join(p.read_bytes() for p in inputs)).hexdigest()[:16]
        binary = BUILD / f'zx02-{digest}'
        BUILD.mkdir(exist_ok=True)
        if not binary.exists():
            subprocess.run(['cc', '-O3', '-DNDEBUG', '-o', str(binary),
                            *(str(SOURCE / name) for name in
                              ('compress.c', 'optimize.c', 'memory.c', 'zx02.c'))], check=True)
        _COMPRESSOR = binary
    return _COMPRESSOR


def encode(data):
    """Return a ZX02 stream, or None if storing raw bytes is smaller."""
    data = bytes(data)
    if not data:
        return None
    if data not in _CACHE:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'input'
            output = Path(directory) / 'output'
            source.write_bytes(data)
            subprocess.run([str(compressor()), str(source), str(output)], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            encoded = output.read_bytes()
        _CACHE[data] = encoded if len(encoded) < len(data) else None
    return _CACHE[data]


def decode(data, size=None):
    """Decode standard forward ZX02, optionally stopping at an output bound."""
    at = 0
    reservoir = 0x80
    extra = None
    out = bytearray()
    offset = 1

    def byte():
        nonlocal at
        if at >= len(data):
            raise ValueError('truncated ZX02 stream')
        value = data[at]
        at += 1
        return value

    def bit():
        nonlocal reservoir, extra
        if extra is not None:
            value, extra = extra, None
            return value
        if reservoir == 0x80:
            value = byte()
            reservoir = ((value << 1) | 1) & 255
        else:
            value = reservoir
            reservoir = (reservoir << 1) & 255
        return value >> 7

    def elias():
        value = 1
        while bit():
            value = (value << 1) | bit()
            if value > 256:
                raise ValueError('invalid ZX02 Elias code')
        return value

    state = 0
    while size is None or len(out) < size:
        if state == 0:
            length = elias()
            for _ in range(length):
                out.append(byte())
                if size is not None and len(out) == size:
                    return bytes(out)
            state = 2 if bit() else 1
        else:
            add = 0
            if state == 2:
                high = elias()
                if high == 256:
                    break
                low = byte()
                offset = ((high - 1) << 7) + (low >> 1) + 1
                extra = low & 1
                add = 1
            length = (elias() + add) & 255
            if not length:
                length = 256
            if offset > len(out):
                raise ValueError('ZX02 match precedes output')
            for _ in range(length):
                out.append(out[-offset])
                if size is not None and len(out) == size:
                    return bytes(out)
            state = 2 if bit() else 0
    if size is not None and len(out) != size:
        raise ValueError(f'decoded {len(out)} of {size} ZX02 bytes')
    return bytes(out)
