# Wizardry I for Atari 8-bit

An unofficial Atari XL/XE port of **Wizardry: Proving Grounds of the Mad Overlord**, targeting the 64 KB Atari 65XE. A new 6502 runtime runs the original Apple II game's Pascal p-code, with the animated title in colour, colour monster pictures adapted from the PC Engine version, and music adapted from the NES version for Atari POKEY.

## Screenshots

| Animated title | Monster encounter |
| --- | --- |
| ![Wizardry title animation running on Atari800](src/port/atari/screenshots/title.png) | ![Colour rogue encounter with party commands and roster](src/port/atari/screenshots/encounter.png) |

Watch [Wizardry 1 port to Atari 8bit](https://www.youtube.com/watch?v=1cHdtRZdmj8) on [grazzt519's YouTube channel](https://www.youtube.com/@grazzt519).

## Download and disk format

Download **[wizardry.atr](wizardry.atr)**. Everything needed by the game is in this **one bootable ATR**: the runtime, title, game, scenario, pictures and music. No separate boot disk, scenario disk, save disk, DOS disk or asset downloads are required.

The image contains both original Apple II disk volumes and switches between them automatically. When the game asks for the boot or scenario disk, leave this ATR mounted and press **RETURN**.

This build is **486,544 bytes** (about 475 KiB): a 16-byte ATR header plus **3,801 sectors of 128 bytes**. It is an oversized disk image, so it does **not** fit on a standard 90 KB or 130 KB Atari floppy. For real hardware, an ATR-capable disk device would need to support this sector count and writes; that setup has not been verified.

## How to play

1. Keep the downloaded ATR as a master and make a copy for playing, such as `wizardry-play.atr`.
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

**Your characters and progress are saved inside the ATR you play on.** Keep it writable, retain that same file between sessions, and back it up while the emulator is closed. If your emulator buffers disk changes, save or flush them before closing it. Replacing your play copy with a fresh download replaces your saved game too.

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

## Source code and development

The [src/ folder](src/README.md) contains the Atari port's source code, development tools, tests and research documentation. Start with its [build instructions](src/README.md#build-from-source) to build the game yourself.

| Path | Contents |
| --- | --- |
| [src/port/atari/](src/port/atari/README.md) | 6502 assembly runtime, build scripts, picture and music converters, emulator tests and screenshots |
| [src/tools/](src/tools) | Pascal disk and p-code tools, host reference p-machine, scenario utilities, and toolchain/emulator setup |
| [src/RESEARCH.md](src/RESEARCH.md) | Research findings, reference catalog and provenance |
| [src/SPEC.md](src/SPEC.md) | Port design and fidelity requirements |

Run the development commands from `src/` after cloning the repository:

```sh
cd src
```

Building and running the regression tests requires external Apple II disk files, listed in the [build prerequisites](src/README.md#build-from-source). Disk images, PDF books, the two C64 book transcriptions, NES music and downloaded PC Engine sprites are excluded from `src/`. The downloadable `wizardry.atr` at the repository root is the ready-to-play build.

## Credits

Original Wizardry by Andrew Greenberg and Robert Woodhead / Sir-Tech. Pascal and assembly reconstruction by Thomas William Ewers; restored scenario by Snafaru. Music from the NES version by Kentaro Haneda. Monster artwork uses Jun Suemi's designs as depicted in the PC Engine version.

Wizardry and the original game, music and artwork belong to their respective rights holders. This is an unofficial fan port.
