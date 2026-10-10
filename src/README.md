# Wizardry I for Atari 8-bit

An unofficial Atari XL/XE port of **Wizardry: Proving Grounds of the Mad Overlord**, targeting the 64 KB Atari 65XE. A new 6502 runtime runs the original Apple II game's Pascal p-code, with the animated title in colour, colour monster pictures adapted from the PC Engine version, and music adapted from the NES version for Atari POKEY.

This source package lives in the GitHub project's `src/` directory. Paths in this README are relative to `src/` unless stated otherwise.

## Gameplay video

Watch [Wizardry 1 port to Atari 8bit](https://www.youtube.com/watch?v=1cHdtRZdmj8) on [grazzt519's YouTube channel](https://www.youtube.com/@grazzt519).

## Screenshots

| Animated title | Monster encounter |
| --- | --- |
| ![Wizardry title animation running on Atari800](port/atari/screenshots/title.png) | ![Colour rogue encounter with party commands and roster](port/atari/screenshots/encounter.png) |

These screenshots show a build with the optional PC Engine monster artwork. A build without those assets uses the original Apple II pictures.

## Disk format

Build `port/atari/build/wizardry.atr` using the instructions below. The result is **one bootable ATR** containing the runtime, title, game and scenario, plus any optional pictures and music included at build time. No separate boot, scenario or save disk is needed to play. Generated ATRs are not included in this source tree.

The image contains both original Apple II disk volumes and switches between them automatically. When the game asks for the boot or scenario disk, leave this ATR mounted and press **RETURN**.

The illustrated build with music and monster artwork is **486,544 bytes** (about 475 KiB): a 16-byte ATR header plus **3,801 sectors of 128 bytes**. Size varies with the optional assets. It is an oversized disk image, so it does **not** fit on a standard 90 KB or 130 KB Atari floppy. For real hardware, an ATR-capable disk device would need to support this sector count and writes; that setup has not been verified.

## How to play

1. Keep the built ATR as a master and make a copy for playing, such as `wizardry-play.atr`.
2. In your Atari emulator, select **800XL or 65XE / XL-XE**, **64 KB RAM**, **BASIC disabled**, and **NTSC** (the tested video mode).
3. Mount the play copy in **drive 1 / D1:** with **disk writes enabled**, then boot it.
4. At the options screen after the title, press **S** to start.

For Atari800, the equivalent command is:

```sh
atari800 -xl -ntsc -nobasic -no-kbdjoy0 -no-kbdjoy1 wizardry-play.atr
```

On Windows, use `atari800.exe` in place of `atari800`. In other emulators, including Altirra, use the same machine and disk settings. Disable keyboard-to-joystick mappings so that letter keys reach the game.

Use the keyboard and the letter commands shown on each screen; **RETURN** confirms prompts. Create characters in the Training Grounds, assemble a party at Gilgamesh's Tavern, equip them at Boltac's, and enter the maze from the Edge of Town.

## Saving and returning to your party

**Your characters and progress are saved inside the ATR you play on.** Keep it writable, retain that same file between sessions, and back it up while the emulator is closed. If your emulator buffers disk changes, save or flush them before closing it. Replacing your play copy with a fresh build replaces your saved game too.

Return to town before ending a session. The original game does not provide a save-and-resume checkpoint inside the maze.

If you reset or close the emulator while exploring, characters may be marked **OUT**. To recover that interrupted expedition:

1. Boot to the options screen and choose **U)tilities**, then **R)ecover**.
2. Press **RETURN**, then **RETURN** again at “PLACE SCENARIO IN DRIVE 1”. Leave the same ATR mounted.
3. After recovery, press **RETURN**, choose **L)eave**, then **S)tart**.

Recovered characters return to their state when they entered the maze, with no ten-year ageing penalty. Characters killed or deliberately disbanded in the maze require an in-game rescue; this utility does not retrieve them.

## Current status

Development build, October 10, 2026. Tested in Atari800 against a reference implementation through character creation, saving, town services, maze exploration and extended combat sessions, including byte-for-byte comparisons of saved scenario data.

- A complete playthrough has not yet been verified. Deeper dungeon levels, trapped chests, actual level gains, resurrection and item identification still need testing.
- **M)ake scenario disk** and **U)pdate** require a second drive and are unsupported. Other utilities besides Recover remain untested. Start a new game by copying the master ATR.
- Real Atari hardware and PAL operation have not been verified.
- Each monster has its own picture, which can reveal its identity before the party identifies it.

## Build from source

Start in the GitHub repository's root and enter `src/` as shown below. Run subsequent build and test commands from `src/` unless a command explicitly changes directories. The setup scripts target Linux/WSL. Use Python 3.10 or newer, `git`, `curl`, GCC, Make and `unzip`.

Disk images are **not included**. Before building, supply these files locally:

- `appleII/images/wizardry_i/wizardry_i_boot.dsk`
- `appleII/images/wizardry_i/snafaru_restored_scenario.dsk`

The regression tests and demo also use `appleII/images/wizardry_i/wizardry_i_scenario.dsk` (the played scenario). UCSD tests additionally need the five Ewers source/build disks at the paths recorded in [the source manifest](appleII/source/ewers_wizardry_i/SOURCES.json). Original source URLs and expected hashes are preserved in [the game disk manifest](appleII/images/wizardry_i/SOURCES.json). These files remain ignored by Git when supplied locally.

```bash
cd src
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
tools/toolchain/setup.sh
python3 port/atari/build.py
```

The build uses ca65/ld65 from the local toolchain and the Apple II disks supplied locally as described above. It works without the optional music and replacement artwork. The Python dependencies are NumPy and Pillow, used by the picture converter.

For the illustrated monster pictures, fetch the optional assets before building:

```bash
python3 port/atari/pictures.py --fetch
python3 port/atari/build.py
```

For music, supply the NES version's NSF at `nes/snafaru/wiz1.nsf` before building. Downloaded artwork, NES music, converted caches and build outputs are ignored by Git. See the [picture and music documentation](port/atari/README.md#pictures) for details and credits.

To rebuild while preserving a party saved on an earlier ATR:

```bash
python3 port/atari/build.py --scenario /path/to/wizardry-play.atr
```

The new disk is written to `port/atari/build/wizardry.atr`; back up the old play disk first.

## Tools and tests

After supplying the external disk fixtures above, the Python reference tools can be tested without installing emulators:

```bash
(cd tools && python3 -m unittest discover -s ucsd/tests -t .)
(cd tools && python3 -m unittest discover -s pvm/tests -t .)
```

For Atari emulator tests, install the [emulator tools](tools/emulators/README.md#rebuilding), including `libatari800`. Their setup also needs Node, `dpkg-deb`, SDL2 development headers and GTK3 runtime libraries.

```bash
tools/emulators/setup.sh
python3 port/atari/build.py --test-images
python3 -m unittest discover -s port/atari/tests -t port/atari
```

The tests compare the Atari runtime against the host p-machine, including screens and saved scenario bytes. Demo recording additionally requires FFmpeg; see [the Atari testing notes](port/atari/README.md#testing).

## Source directory guide

All paths below are inside the repository’s `src/` directory. For example, the built disk is `src/port/atari/build/wizardry.atr` when addressed from the repository root.

| Path | Contents |
| --- | --- |
| [port/atari](port/atari/README.md) | Atari assembly runtime, build and asset converters, emulator harness, lockstep tests and screenshots |
| [tools/ucsd](tools/ucsd/README.md) | Apple Pascal disk reader, code-file parser, p-code and 6502 analysis |
| [tools/pvm](tools/pvm/README.md) | Host reference p-machine and regression tests |
| [tools/wizardry_scenario.py](tools/wizardry_scenario.py) | Scenario tables, roster inspection and record comparisons |
| [tools/nes/nsf.py](tools/nes/nsf.py) | NSF playback and music analysis utility |
| [tools/toolchain](tools/toolchain/README.md) | Reproducible local cc65 and CiderPress II setup |
| [tools/emulators](tools/emulators/README.md) | Emulator setup, launchers and optional MCP configuration |
| [appleII](appleII/README.md) | Apple II references, external disk manifests, reconstructed Pascal/assembly listings and provenance |
| [atari](atari/README.md), [c64](c64/README.md), [common](common/README.md) | Platform manuals, format references and shared 6502/cc65 documentation |
| [SPEC.md](SPEC.md) | Port design and fidelity requirements |
| [RESEARCH.md](RESEARCH.md) | Research catalog, findings and reference-library instructions |
| [test-artifacts/emulators](test-artifacts/emulators) | Reference emulator screenshots and recorded protocol checks |

Disk images, PDF books and the two C64 book transcriptions are omitted. The book transcriptions remain catalogued for provenance but are not fetched by the reference helper. Large reference PDFs are optional local downloads. Restore them with `python3 tools/fetch_refs.py`; source URLs and checksums are recorded in each library's `SOURCES.json` and `SHA256SUMS`. They are optional for building the game. Local tool installations, working save disks and personal session settings are excluded.

## Credits

Original Wizardry by Andrew Greenberg and Robert Woodhead / Sir-Tech. Pascal and assembly reconstruction by Thomas William Ewers; restored scenario by Snafaru. Music from the NES version by Kentaro Haneda. Monster artwork uses Jun Suemi's designs as depicted in the PC Engine version.

Wizardry and the original game, music and artwork belong to their respective rights holders. This is an unofficial fan port.
