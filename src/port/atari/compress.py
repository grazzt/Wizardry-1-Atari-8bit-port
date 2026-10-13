"""LZSS for the two-disk scenario and PCE graphics.

Groups of eight tokens follow one flag byte (MSB first; 1 = literal).
Literals hold one byte. Two-byte little-endian matches pack offset-1 in
11 bits and length-3 in 5 bits: a 2,048-byte window, lengths 3..34. Every
unit is independent; overlapping matches refer to already decoded output.
The encoder chooses the minimum byte cost including flag groups and returns
None when raw storage is smaller. The 6502 decoder lives in src/lzss.s.
"""

WIN = 2048
MINMATCH = 3
MAXMATCH = 34


def lzss_encode(data):
    """Choose the smallest token sequence, including each group's flag byte."""
    n = len(data)
    matches = [(0, 0)] * n
    head, chain = {}, [-1] * n
    for i in range(n - 2):
        key = bytes(data[i:i + 3])
        j = head.get(key, -1)
        best, offset = 0, 0
        while j >= 0 and i - j <= WIN:
            length = 3
            while length < MAXMATCH and i + length < n and data[j + length] == data[i + length]:
                length += 1
            if length > best:
                best, offset = length, i - j
                if length == MAXMATCH:
                    break
            j = chain[j]
        matches[i] = best, offset
        chain[i] = head.get(key, -1)
        head[key] = i
    # dp[phase][i]: byte cost from i with phase tokens already in the group.
    dp = [[0] * (n + 1) for _ in range(8)]
    choices = [[1] * n for _ in range(8)]
    for i in range(n - 1, -1, -1):
        best, _ = matches[i]
        for phase in range(8):
            tail = dp[(phase + 1) % 8]
            cost, step = 1 + tail[i + 1], 1
            for length in range(3, best + 1):
                candidate = 2 + tail[i + length]
                if candidate < cost:
                    cost, step = candidate, length
            dp[phase][i] = cost + (phase == 0)
            choices[phase][i] = step
    if dp[0][0] >= n:
        return None
    out = bytearray()
    i = 0
    while i < n:
        flag_at = len(out)
        out.append(0)
        for phase in range(8):
            if i >= n:
                break
            length = choices[phase][i]
            if length == 1:
                out[flag_at] |= 0x80 >> phase
                out.append(data[i])
            else:
                token = (matches[i][1] - 1) << 5 | (length - 3)
                out.extend((token & 255, token >> 8))
            i += length
    return bytes(out)


def lzss_decode(data, size=None):
    """The reference decoder (mirrors src/lzss.s). `size` bounds the output."""
    out = bytearray()
    i = 0
    while i < len(data) and (size is None or len(out) < size):
        flag = data[i]
        i += 1
        for bit in range(7, -1, -1):
            if i >= len(data) or (size is not None and len(out) >= size):
                break
            if flag >> bit & 1:
                out.append(data[i])
                i += 1
            else:
                v = data[i] | data[i + 1] << 8
                i += 2
                off = (v >> 5) + 1
                length = (v & 31) + MINMATCH
                if off > len(out):
                    raise ValueError('LZSS match precedes the output')
                for _ in range(length):
                    if size is not None and len(out) >= size:
                        break
                    out.append(out[-off])
    if size is not None:
        assert len(out) == size, f'decoded {len(out)} of {size}'
    return bytes(out)
