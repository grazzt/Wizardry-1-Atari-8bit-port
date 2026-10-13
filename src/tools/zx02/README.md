# ZX02 compressor source

Vendored from https://github.com/dmsc/zx02 at revision
`7ffa0e782c9f5718a8d77ba021c6babc78c7fe19`.

The upstream sources are unchanged. `port/atari/zx02.py` builds the host
compressor into the ignored Atari build directory using the system C compiler.
Both upstream licenses are retained here. The adapted streaming, bounded
6502 decoder is `port/atari/src/zx02.s`.
