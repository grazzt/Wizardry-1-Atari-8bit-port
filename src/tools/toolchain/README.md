# Cross-development toolchain

| Tool | Version | Use |
| --- | --- | --- |
| [cc65](https://cc65.github.io/) (`cl65`, `ca65`, `ld65`, `da65`, …) | master at `2ea1df8b` (2026-09-20) | Atari 6502 assembly/C, linking, and disassembling Apple native code. The last tagged release, V2.19, dates from 2020; the project ships from master. |
| [CiderPress II](https://ciderpress2.com/) `cp2` | 1.2.0, self-contained linux-x64 | Disk-image inspection and extraction (Apple Pascal, DOS 3.3, ProDOS; also creates and edits images) |

Both are installed under this directory and ignored by Git. Rebuild after cloning, starting from the GitHub repository root. The package lives under `src/`; subsequent commands use that directory as their working directory:

```bash
cd src
./tools/toolchain/setup.sh          # about 10 seconds plus downloads; safe to re-run
source tools/toolchain/env.sh       # put cl65/ca65/ld65/da65/cp2 on PATH and set CC65_HOME
```

Pins and hashes are in [SOURCES.json](SOURCES.json). The setup script needs `git`, `curl`, `gcc`/`make` and `unzip`.

**Verified 2026-10-09.**

- `cl65 -t atari` built a C "hello" program into an Atari `.xex`.
- `cp2 catalog` lists the Wizardry boot disk.
- `cp2 extract` produces the same `WIZARDRY.CODE`, `SCENARIO.DATA` and `SCENARIO.MESGS` bytes as the project's own [`ucsd`](../ucsd/README.md) reader.

Documentation: [ca65](../../common/tools/ca65.html), [ld65](../../common/tools/ld65.html), [da65](../../common/tools/da65.html), the [cc65 Atari target](../../atari/tools/atari.html), and the [CiderPress II CLI manual](../../appleII/tools/CiderPress_II_CLI_Manual.md).
