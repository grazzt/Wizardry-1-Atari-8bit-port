# Wizardry I port research library

This catalog describes the original research collection. Disk images, PDF books and the two C64 book transcriptions are not included in this public source tree. Source URLs and checksums are retained; see [build prerequisites](README.md#build-from-source) for the external disks needed by the tools and tests.

Collected 2026-10-09 for investigating a port of Wizardry I to Atari 8-bit computers. The proposed approach is in [SPEC.md](SPEC.md).

The [Atari port](port/atari/README.md) running in Atari800: the original title animation, and an encounter.

| Title | Encounter |
| --- | --- |
| ![Wizardry title screen on the Atari: the Wizardry logo, the wizard rising from the cauldron's smoke](port/atari/screenshots/title.png) | ![An encounter on the Atari: a rogue with a sword, in colour, beside the party's options and roster](port/atari/screenshots/encounter.png) |

## Books consulted

The C64 research used the *Commodore 64 Programmer’s Reference Guide* (Commodore; Project 64 text transcription) and *Mapping the Commodore 64* (Sheldon Leemon, Compute! Publications, 1984; Project 64 text transcription). They informed the memory-map, ROM-call and hardware-register references in the [C64 reading guide](c64/README.md).

Their text is not distributed in this repository, and the reference-download helper skips both transcriptions. The original source records and hashes remain in `c64/SOURCES.json` and `c64/SHA256SUMS` to document the editions used.

## After cloning

This collection lives under `src/` in the GitHub repository. Start from the repository root; paths elsewhere in this guide are relative to `src/`.

```bash
cd src
python3 tools/fetch_refs.py        # reference PDFs (not stored in Git), verified by SHA-256
tools/emulators/setup.sh           # VICE, Atari800, Apple II web emulator, MCP servers
tools/toolchain/setup.sh           # cc65 and CiderPress II
```

## Contents

| Path | Contents |
| --- | --- |
| [appleII/images/wizardry_i](appleII/images/wizardry_i/README.md) | Apple II Wizardry I disk images, provenance and analysis |
| [appleII/source/ewers_wizardry_i](appleII/source/ewers_wizardry_i/README.md) | Thomas William Ewers's reconstructed Pascal/assembler source, verified against those images |
| [c64/images/wizardry_i](c64/images/wizardry_i/README.md) | C64 Wizardry I disk images |
| [tools/ucsd](tools/ucsd/README.md) | Python tools for Apple Pascal disks, code files, p-code and native 6502 procedures |
| [port/atari](port/atari/README.md) | **The Atari 65XE port**: a 6502 p-machine running the original `WIZARDRY.CODE`; plays through character creation, the maze and battles identically to the host p-machine |
| [tools/pvm](tools/pvm/README.md) | Host p-machine that runs the real `WIZARDRY.CODE` (native routines in a 6502 emulator) as a reference |
| [tools/wizardry_scenario.py](tools/wizardry_scenario.py) | Reads `SCENARIO.DATA`: table of contents, roster, record-level diffs |
| [tools/emulators](tools/emulators/README.md) | Emulator launchers, MCP servers (Claude Code via [.mcp.json](.mcp.json), or Codex) |
| [tools/toolchain](tools/toolchain/README.md) | cc65 and CiderPress II |
| Reference libraries below | Manuals and format documentation per platform |

Each image set has separate provenance notes and checksums; the reference-document counts below exclude disk images.

| Platform | Local reference files | Start here |
| --- | ---: | --- |
| Atari 8-bit — target | 12 | [Atari reading guide and catalog](atari/README.md) |
| Apple II — possible source | 16 | [Apple II reading guide and catalog](appleII/README.md) |
| Commodore 64 — possible source | 8 | [C64 reading guide and catalog](c64/README.md) |
| Shared 6502 and cc65 | 4 | [Common reading guide and catalog](common/README.md) |

These are downloaded PDFs, text documents, and HTML/Markdown snapshots, organized into `manuals/`, `programming/`, `disk/`, and `tools/` directories. The MOS 6502 programming manual and ca65/ld65/da65 documentation are stored once in `common/`.

**PDFs are not stored in Git** (they total about 480 MB). From `src/`, run `python3 tools/fetch_refs.py` to download them from their original URLs and verify each SHA-256; `--check` verifies without downloading.

## Findings so far (2026-10-09)

The [Wizardry.Code reconstruction project](https://github.com/snafaru/Wizardry.Code) documents an Apple II UCSD Pascal 1.1 build of Wizardry's `WIZARDRY.CODE` and `SYSTEM.STARTUP`. Its current v3.2 includes changes to the game, so it should be treated as a research lead rather than an untouched original. Its README is [saved locally](appleII/programming/Wizardry_Reconstruction_README.md). The underlying Ewers reconstruction is now saved and checked:

- **Ewers's listings match our boot disk exactly.** All 7,713 statement offsets in the two compiler listings land on instruction boundaries in our binaries, and the `WIZARDRY.CODE` segments are byte-identical to his build. See the [source notes](appleII/source/ewers_wizardry_i/README.md).
- **Disk provenance is resolved.**
  - The boot disk is byte-identical to the archive's "Original" boot disk, with copy protection patched out.
  - Our scenario disk is a *played* copy with 20 characters on it.
  - A clean-roster scenario disk was added. See the [image notes](appleII/images/wizardry_i/README.md).
- **Very little code is machine-specific.** In the [p-code analysis](tools/ucsd/README.md), only the game's own interpreter/BIOS (`RTSTRP.APPLE`, 12 KB) and seven native routines (1,094 bytes) depend on the Apple. The game logic and the Pascal OS are portable p-code.
- **Memory looks favourable.** The resident code plus the largest overlay totals 11,176 bytes. The game uses no floating point and allocates no heap.
- **The game's runtime is identified.** `RTSTRP.APPLE` is a stripped p-machine: no REAL or SET operations, and 110 opcodes in all. See the [runtime notes](appleII/images/wizardry_i/README.md#the-runtime-rtstrpapple).
- **The game runs on the host.** The [host p-machine](tools/pvm/README.md) plays it from the title sequence through character creation, saving, the maze and battles. Peak memory measured so far is 15.8 KB of stack, including loaded code.
- **The Atari port plays it.** [port/atari](port/atari/README.md) boots into the original title animation (in colour, and with the NES version's music: the title theme, and each place's theme in the game) and options screen, with U)tilities R)ecover for characters left in the maze, then the game, where every monster has its own colour picture, converted from the PC Engine version's sprites. It matches the host p-machine key by key, through thousands of keys of play.

Remaining questions are listed in [SPEC.md](SPEC.md#status-and-next-steps).

## Using the collection

- Each platform's `README.md` explains the documents and links both local copies and their sources.
- `SOURCES.json` records retrieval date, source URLs, byte sizes, SHA-256 hashes, PDF page counts, and any local HTML-link adjustments.
- `SHA256SUMS` includes the reference files and their supporting web assets. From a platform folder, after supplying the external files, run `sha256sum -c SHA256SUMS` to check the saved copies, or run `python3 tools/fetch_refs.py --check` to check every library at once.
- HTML document bodies and their required local styles are saved. Links to documents outside this collection lead back to the original websites and require internet access. Markdown snapshots may also link to upstream resources.
- Some PDF scans have no searchable text layer. A PDF viewer is needed to read those pages; no OCR has been added.
- Original copyright and licence notices remain in the files. The CiderPress format notes are by faddenSoft and are distributed under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/); local HTML changes only repair links for this collection.

## Additional research lead

[Neil Parker's Undocumented Secrets of Apple Pascal](https://llx.com/Neil/a2/passec.html) is listed as an online follow-up. The host returned an access-check page during collection, so it is **not** included as a local document.
