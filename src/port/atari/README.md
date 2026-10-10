# Wizardry I for the Atari 65XE

This is a p-machine written in 6502 assembly that runs the unmodified Apple `WIZARDRY.CODE` on a 64 KB Atari XL/XE. The target is the 65XE; Atari800 runs it as an 800XL, which is the same machine for our purposes. The Apple runtime it replaces, and the reference it is tested against, are described in [`tools/pvm`](../../tools/pvm/README.md).

The source package lives under the repository’s `src/` directory. Start these commands from the repository root; after `cd src`, all build and asset paths below are relative to that directory. Supply the external disks described in the [source package README](../../README.md#build-from-source) first.

```bash
cd src
python3 port/atari/pictures.py --fetch      # once: the redrawn monster pictures' sprites (see Pictures)
python3 port/atari/build.py                 # -> port/atari/build/wizardry.atr (bootable)
cp port/atari/build/wizardry.atr /tmp/play.atr     # the game saves to the disk; play on a copy
tools/emulators/bin/atari800 /tmp/play.atr

python3 port/atari/build.py --scenario /tmp/play.atr   # new build, keeping the characters saved on an older disk

python3 port/atari/build.py --test-images  # test.atr, played.atr, title.atr for the tests
python3 -m unittest discover -s port/atari/tests -t port/atari
```

On other emulators, turn off any keyboard-joystick emulation: Atari800's defaults map W/A/S/D and the numeric keypad to joysticks, and those keys then never reach the game. On Windows use `atari800.exe -xl -nobasic -no-kbdjoy0 -no-kbdjoy1 wizardry.atr`, or simply open `wizardry.atr` in Altirra or Atari800 with an XL/XE, 64 KB, BASIC off configuration. The disk must be writable: the game saves to it.

### Characters marked OUT

The training grounds roster (`*ROSTER`) marks a character **OUT** in two cases:

- **The emulator was closed, or the machine reset, while the party was in the maze.** The game has no save in the maze: entering it writes each member as "in the maze", and only coming back to town clears that. To bring them back, choose U)tilities on the options screen after the title, then R)ecover, RETURN, and RETURN again at "PLACE SCENARIO IN DRIVE 1" (the port swaps the disk itself). Each character comes back as they were when they entered the maze, with no ageing penalty ("NO 10 YEAR PENALTY"). Then RETURN, L)eave, and S)tart. Builds before 2026-10-09's fix loop forever at that prompt: rebuild with `--scenario your-old.atr` to move your characters onto a fixed disk.
- **The party died, or was D)isbanded in camp.** Those characters stay where they fell, and Recover does not touch them. A new party goes to the same spot and uses I)nspect to find them and pick them up. The dead then need the temple. Disbanding also ages each character.

Needs the toolchain (`tools/toolchain/setup.sh`) for ca65/ld65, and `libatari800` (`tools/emulators/setup.sh`) for the tests.

## Status (2026-10-10)

- **The castle.** It boots, finds `SCENARIO.DATA` with the game's own directory search, loads the table of contents and character set, and shows the castle.
- **The original start-up runs, with the title in colour.** `SYSTEM.STARTUP` shows "PREPARE YOURSELF / FOR THE ULTIMATE / IN FANTASY GAMES", the animated title (the wizard, the smoke from the cauldron, the scrolling *Wizardry* logo with its colour flips), and the copyright and options screen ("VERSION 2.1 OF 22-JAN-82"). S)tart chains to the game. The options screen and the screens after chaining match `pvm`. U)tilities R)ecover works and matches `pvm`, including the save. The other utilities are untested; M)ake scenario disk and U)pdate need a second drive, which the port does not have.
- **Everything played so far matches the host p-machine exactly**, key by key:
  - character creation, keeping and saving, with the bonus-point roll identical;
  - the character record written to disk, identical down to age, gold and hit points;
  - forming a party, entering the maze, the 3D maze view and walking;
  - an encounter with the monster picture and the group list;
  - a full battle round, death, and the cemetery;
  - a 313-key adventure with a six-character party from the played scenario disk: character sheet and spell books (`UTILITIE`), buying and selling at Boltac's, resting at the inn, `DIOS` cast in camp, 97 moves through the maze, a battle won, the walk back, the stairs to the castle, and leaving the game, which saves. The saved scenario data is byte-identical to `pvm`'s;
  - a 3,005-key session (about 51 minutes of emulated play): 20 battles with `BADIOS` and `HALITO` cast in combat (`CASTASPE`) until spell points run out, a friendly encounter, the walk back, the inn for all six characters, and the temple. The save is again byte-identical.

  The comparison covers text screens, display mode and the bitmap: the Apple hi-res page mapped to the Atari layout is identical row for row.
- **Music from the NES version.** The title theme ("Opening", by Kentaro Haneda) plays over the title and options screens. In the game each place has its NES theme: castle, tavern, Boltac's, inn, temple, edge of town, maze, camp, combat and the cemetery. Jingles mark encounters, victories, level-ups and the temple's rites. It needs the NES music file in `nes/`, which is kept out of Git (see [Music](#music)); without it the build is silent.
- **Every monster has its own colour picture.** The Apple's 20 line drawings, mostly white, are replaced by Jun Suemi's monsters as drawn for the PC Engine version (the designs the NES version also uses), converted to what the Atari can show beside sharp text (see [Pictures](#pictures)). The chest and the gold are the Apple's pictures, tinted. It needs the sprites in `art/pce/`, which are kept out of Git; without them the Apple's pictures are shown in their artifact colours. The tests check each picture that appears, pixel for pixel, and the rest of the screen still matches `pvm` key by key.
- **All seven native routines are implemented.** `DRAWLINE` and `CLRPICT` reproduce the Apple maze drawing, including its clipping comparisons.
- **Size.** The runtime is 6.2 KB of code plus 1.0 KB of tables, about half the Apple's 12 KB `RTSTRP.APPLE`, because it implements only what the game uses.
- **Not yet exercised:** traps on chests (the demo run opens a trapless one), actually gaining a level, raising the dead at the temple, identifying items, and deeper maze levels.

## Design

| Part | Choice |
| --- | --- |
| Instructions | The 55 opcode families `WIZARDRY.CODE` uses; others raise execution error 11, as the Apple runtime does for the ones it strips. Comparisons: integer, string equality and multi-word inequality only. |
| Evaluation stack | The 6502 hardware stack, as on the Apple: words are pushed high byte first, so native routines take arguments with `PLA`. |
| Frames | 12-byte mark-stack word (static link, dynamic link, return IPC, caller's and own JTAB, segment numbers) followed by parameters, then locals. The conventions match `pvm`. |
| Code segments | Read from disk onto the memory stack at first call, freed when their last activation returns. Segment 1 stays resident. |
| Disk | One bootable single-density ATR (3,801 sectors with the music and the pictures). The OS boot loader reads the runtime from the boot sectors to `$06FA`; a short boot routine reads the high area (tables and extra code) to `$B000` and starts through `DOSVEC`. Two Apple Pascal volumes follow, each 280 blocks as 1,120 sectors:<br>• the **boot disk**, with `SYSTEM.STARTUP` and the title picture file `WT`. It is drive 1 while the title and options run, and is write-protected: `OPTIONS` checks for error 16.<br>• the **scenario disk**, which becomes drive 1 when `SYSTEM.STARTUP` chains to `WIZARDRY.CODE`, as if the player swapped disks.<br>The utilities ask for disk swaps too, so drive 1 also switches as their prompts start: `RDSCNTOC` ("PLACE SCENARIO IN DRIVE 1") brings in the scenario, and `EXITUTIL` ("PLACE BOOT DISK IN DRIVE 1") the boot disk. `pvm` does the same. Code segments always load from the running program's own volume (`codebase`).<br>For drive 1's volume, Pascal block *n* is at sectors `volbase`+4*n* to +4*n*+3. `build.py` assembles twice to fix the layout and writes it to `build/layout.json`. It contains `WIZARDRY.CODE`, `SCENARIO.DATA` and `SCENARIO.MESGS`, so the game's file lookup works unchanged. A partial final sector goes through a buffer, so segment loads never overwrite the frame above them. |
| Console | 40×24 ANTIC mode 2 screen with its own display list, and the Apple Pascal control codes. The keyboard is read through CIO `K:`; RETURN becomes 13, upper case. |
| Graphics | 320×192 mode F at `$2000`, with a second LMS at line 102 for the 4K boundary. Each Apple hi-res byte becomes one Atari byte in the same column: 7 pixels become 8, with the last pixel doubled. Text and lines keep their positions, slightly stretched horizontally, as the [fidelity rules](../../SPEC.md#fidelity-what-must-match-and-what-may-differ) allow. |
| Randomness | `RANDOM` is the Apple algorithm on the same 4 state bytes, stirred while waiting for keys as on the Apple. |
| Apple hi-res in p-code | The game computes Apple hi-res addresses itself in three places: the monster picture (`CINIT.2`), the treasure picture (`REWARDS.2`) and scrolling the monster-group list (`CUTIL.30`). It moves bytes there with `MOVELEFT`/`FILLCHAR`. Any such transfer touching `$2000`–`$3FFF` is done byte by byte in Apple terms: bytes read back from the screen are converted to Apple form, and bytes written are expanded and placed at the Atari position of the same row and column. Screen-hole bytes are dropped. |
| Title colour | The Apple's artifact colours are reproduced in ANTIC mode E (160×192, 4 colours) while `SYSTEM.STARTUP` runs ([`src/color.s`](src/color.s)).<br>• Apple bytes go to a shadow buffer; changed 2-byte groups are redrawn with lookup tables. A lit dot beside a lit dot is white; a lone dot is purple/green or blue/orange by column parity and palette bit, one Atari pixel per dot pair.<br>• Each band of 8 lines shows black, white and its two most frequent hues, loaded by a display-list interrupt (per-line interrupts would nest, since mode E lines are one scanline tall). Rarer hues use the nearest chosen one.<br>• The hues are the Atari colours closest to the Apple's in Atari800's palette: purple `$6x`, green `$Cx`, blue `$Ax`, orange `$3x`. The pictures use the same hues.<br>• The logo's palette flip just swaps band colours.<br>• The animation runs about 2–3× slower than in monochrome. The game itself stays monochrome mode F. |
| Pictures | See [Pictures](#pictures). |
| Apple picture colour | Without the sprites (or with `build.py --pictures apple`), the Apple's own monster and treasure pictures (50 lines of 10 Apple bytes, at lines 23–72, bytes 1–10) are coloured with players and missiles in front of the mode F screen ([`src/picture.s`](src/picture.s)). Text shares those scanlines, so the title's mode E approach would have blurred it.<br>• Measured in Atari800: under a player, a lit hi-res pixel shows the player's hue at PF1's luminance, and an unlit one the player's colour. One player bit covers 2 pixels (a cell). Four players and the missiles as a fifth player (PF3) cover the picture's 40 cells in 5 strips.<br>• The Apple bytes written there are kept in a shadow with their palette bits. Once the last line is written, each cell is classed as black, white (a lit dot beside a lit dot) or the hue of a lone dot. An empty cell between two cells of one hue takes that hue, as the Apple's colour fills it. Coloured cells get a player bit.<br>• Each strip shows the most common hue of each band of 8 lines, set by a display-list interrupt (the same one as for the redrawn pictures). A strip needing two hues in one band shows the more common one.<br>• Anything else drawing over the picture (the maze, `CLRPICT`, text, `CLRRECT`, a new picture) turns the colour off; text mode hides it.<br>• The code is a game overlay loaded at `$4000` when `WIZARDRY.CODE` starts. |
| Music | See [Music](#music). |
| Copy protection | The patches in [`tools/pvm/patches.py`](../../tools/pvm/patches.py) are shared with `pvm` and checked when applied. In the game, `SPECIALS.16` (COPYPROT) becomes 8 bytes of p-code that store the success marker (10 at `$0479`) and exit. In `SYSTEM.STARTUP`, `CHKCOPY` reads the serial number, then jumps to its exit. |
| Start-up | Two programs with separate segment tables. Program 0, `SYSTEM.STARTUP`, gets read-only Pascal file access (`FINIT`/`FOPEN`/`FBLOCKIO`/`FCLOSE` on the boot volume's directory) and `SETCHAIN`. Its p-code reads of the keyboard (`$C000`) and BIOS type-ahead pointers (`$BF18`/`$BF19`) and its soft-switch writes (`$C050`/`$C051`) are mapped to Atari equivalents. `LZDECOMP`, the title-frame decompressor, is ported to write through the same byte mapping. When the program ends after `SETCHAIN`, program 1, `WIZARDRY.CODE`, starts. `build.py --no-title` starts straight in the game. |

### Memory map

| Range | Use |
| --- | --- |
| `$0080`–`$00FF` | p-machine registers and scratch |
| `$0100`–`$01FF` | Evaluation stack |
| `$0479` | Copy-protection marker tested by the castle |
| `$0500`–`$06FF` | Sector buffer, harness interface, call log |
| `$06FA`–`$1FA0` | Boot header (6 bytes) and runtime code (no DOS, so page 7 is free) |
| `$2000`–`$3E0F` | Bitmap (the game also loads 512 bytes at `$2000`) |
| `$4000`–`$52FF` | In the game: the picture overlay (`$4000`), players and missiles (`PMBASE` `$4800`, data from `$4B00`), the Apple picture's shadow (`$5000`, unused with the redrawn pictures), and `--trace`'s buffer (`$5200`). |
| `$5300`–`$AFFF` | Heap start (unused by the game) and p-machine stack: 23 KB for a measured 15.8 KB peak. While `SYSTEM.STARTUP` runs, `$4000`–`$5E0F` holds the title's Apple-byte shadow and `$6000`–`$7FB6` the start-up overlay (file I/O, `LZDECOMP`, colour). The overlay is loaded at boot; the start-up stack, which bottoms out near `$819C`, is kept above `$8000`, and the game reuses all of it. |
| `$B000`–`$B81A` | High area: tables, segment tables for both programs, boot-volume file list, program switching, Apple hi-res translation |
| `$BA00`, `$BB00` | Display lists |
| `$BC00`–`$BFBF` | Text screen |

| `$C000`–`$CFFF` | Under the OS ROM: the music player (`$C000`) and the jingles (`$C200`–`$CF0F`) (see [Music](#music)) |
| `$D800`–`$EFAB` | Under the OS ROM: the current song (the title theme, or a place's theme in the game) |

The OS ROM stays enabled; SIO and the keyboard use it. The RAM under it is switched in only while the music plays a frame or a song is copied there; `$EFAC`–`$FFF9` is still free.

## Pictures

The Apple's monster pictures are 70×50 line drawings that show mostly white; one of 20 serves each of the 101 monsters. With the sprites present, the port shows Jun Suemi's monsters instead, one per monster. The SPEC's fidelity rules allow it: the game itself runs unchanged and never knows.

![An encounter: four rogues, with the rogue in colour in the picture box](screenshots/encounter.png)

- **Source.** The PC Engine version's monster sprites (64×96 pixels, 16 colours), from the [Wizardry Wiki](https://wizardry.wiki.gg/wiki/Category:Proving_Grounds_of_the_Mad_Overlord_PCECD_monster_sprites). They are the designs the NES version uses, drawn with more colours. `pictures.py --fetch` downloads the 93 the scenario's monsters need to `art/pce/`. They are copyrighted and stay out of Git, as does the cache of converted pictures.
- **What the Atari can show.** Text shares the picture's scanlines, so the screen stays mode F: sharp black and white. Colour comes from players and missiles in front of it, as five strips of eight cells (a cell is one colour clock, 2 hi-res pixels). Under a set player bit, an unlit pixel shows the player's colour and a lit pixel the player's hue at the text's luminance (measured in Atari800). So each cell is either black/white or dark/light of its strip's hue, and each strip can change its colour every 4 lines. The light colour is as bright as the text, which washed the pictures out at the text's full white, so the game's white is `$0C` instead of `$0E` when the sprites are there.
- **Conversion** ([`pictures.py`](pictures.py)). A sprite is cropped and scaled to hi-res pixels (a PC Engine pixel is 4/3 as wide; tall sprites shrink to the box's 76 lines). For each strip and band, every one of the 128 player colours is tried; the best gives the least error, counting for each cell the better of black/white and dark/light, with a penalty for the noise a dither between far-apart colours makes. The sprite is also shifted a few pixels to where the strips fit it best. The pixels then come from error diffusion between each cell's two colours. `pictures.py --sheet out.png` writes a preview of every picture. [`atari800_ntsc.json`](atari800_ntsc.json) is Atari800's palette, which the converter matches colours against.
- **The chest and the gold** are the Apple's own pictures with one player colour over them (`TINT` in `pictures.py`).
- **Which picture.** By default every monster has its own. On the Apple a picture tells no more than the unidentified name ("SMALL HUMANOID" is one picture for orcs and kobolds); with one each, the picture shows what a monster is before the party has identified it. `build.py --pictures class` keeps the Apple's behaviour: one picture per unidentified name and Apple picture number, the first such monster's sprite (45 pictures). `--pictures apple` shows the Apple's own.
- **On the disk.** A picture is one sector with its first line, line count, the 5×19 strip colours and a flag per band, then a sector per 8 lines: 11 bitmap bytes and 5 player bytes a line. The 95 pictures take 982 sectors, after the music.
- **In the game** ([`src/picture.s`](src/picture.s)). The game still copies its Apple picture to the screen, with `MOVELEFT`s the runtime already translates. Those bytes are not drawn; they are summed. When the last line has been written, the picture to show is found: for `CINIT` it is the monster in the game's global `ENEMYINX` (group 1), and for `REWARDS` the sum tells the chest from the gold. It is read from the disk into the box (lines 6–81, bytes 1–11), which `CLRPICT` has just cleared, and the players are switched on. As with the Apple pictures, anything else drawing there turns them off.
- **The interrupt.** A display-list interrupt two lines before each band that changes a colour sets the five colour registers. Each must change after its strip on the line before the band and before its strip on the band's first line. Interrupts start up to 6 cycles late, so the handler first waits for the end of its line (`WSYNC`); from there the timing is exact, and a fixed delay puts the first write just behind the first strip. Atari800 is cycle-exact here: the picture matches the converter's prediction pixel for pixel with a delay of 9 to 20 `NOP`s, and the code uses 14. A handler takes about two scanlines, so a picture with all 19 changes costs about 14% of the processor while it shows.
- **Tests.** In the lockstep adventures, whenever a redrawn picture appears it must be the right one, by `pvm`'s `ENEMYINX` or the Apple picture on `pvm`'s screen, and every pixel in the box must be the colour `pictures.py` predicts from the disk record. The bitmap comparison leaves the box out while such a picture shows.

## Music

The Apple version has no music. This port borrows the NES version's (1987, Game Studio / ASCII; Kentaro Haneda). The SPEC's fidelity rules allow extra sound, since it never affects the game.

- **Source.** An NSF rip of the NES soundtrack, from [Snafaru's Wizardry site](https://www.zimlab.com/wizardry/recovered/wizardrygame/pages/downloads.html) (`w1/wiz1nsf.zip`), unpacked to `nes/snafaru/wiz1.nsf`. It is copyrighted and stays out of Git. [`tools/nes/nsf.py`](../../tools/nes/nsf.py) runs the NSF's own player on the project's 6502 emulator, 60 times a second as on the NES, and records the sound chip's registers. The song numbers (from the NSF's playlist) are: 1 Opening, 2 Castle, 3 Gilgamesh's Tavern, 4 Boltac's Trading Post, 5 Adventurer's Inn, 6 Temple of Cant, 7 Edge of Town, 8 Dungeon, 9 Camp, 10 Fight, 11 Werdna, 12 Exterminated, 13 Complete, 14–18 jingles and 19–31 sound effects. Songs 2–12 loop; `nsf.py` finds each loop point.
- **Where each plays.** A cue table in [`music.py`](music.py) names the game procedures (from the Ewers listing) whose call starts a song:

  | Song | Starts when the game calls |
  | --- | --- |
  | Castle | `CASTLE`, or `DSPTITLE` from `CASTLE` (back on the castle menu) |
  | Tavern, Inn | `GILGAMSH`, `ADVNTINN` |
  | Boltac's, Temple, Edge of Town | `BOLTAC`, `CANT`, `EDGETOWN`; also `ROLLER` (the training grounds) |
  | Dungeon, Camp | `RUNMAIN`, `CAMPMEN2` (camp in the maze; inspecting from town keeps the town's song) |
  | Fight | `COMBAT`, after the "An Encounter" jingle from `ENCOUNTR` or `CHENCOUN` |
  | Fanfare (jingle) | `GIVEEXP`: "FOR KILLING THE MONSTERS" (fleeing skips it) |
  | Level Up, Murmur–Chant–Pray–Invoke (jingles) | `MADELEV` at the inn, `DOCANT` at the temple |
  | Exterminated, Complete | `CEMETARY` (the party was wiped out), `CONGRATS` (the game is won) |

  Werdna's own theme is not used yet: his fight comes from a fixed encounter that would have to be told apart from the others. The "Important Item" jingle has no cue.
- **Conversion** ([`music.py`](music.py)). The triangle bass, down to 55 Hz, goes to POKEY channels 1+2 joined as 16 bits at 1.79 MHz. The two pulse voices go to channels 3 and 4 at 64 kHz, mostly within 5–9 cents of pitch (up to about 25 cents on the highest notes). Volumes carry over directly. The pulse duty cycle and the triangle's softer shape do not.
- **Storage.** Each register stream is cut into 6-frame blocks, 8 blocks to a pattern, with an order list. Repeated music then costs only order-list bytes. A song image is a header (pattern count, loop pattern, and table addresses for each stream) and its tables, placed at a fixed address. The themes take 2.4–6.1 KB each, 50 KB in all on the disk, and the four jingles 3.3 KB (`$C200`–`$CF0F`).
- **Playback** ([`src/music.s`](src/music.s), [`src/musicgame.s`](src/musicgame.s)). The boot routine puts the player and jingles under the OS ROM at `$C000`, and the title theme in the song slot at `$D800`. Each vertical blank, the immediate VBI hook switches the ROM out, plays one frame and switches it back. That is safe because nothing is displayed in vertical blank, no display-list interrupt can occur, and IRQs are masked meanwhile. While SIO is busy, the music waits.

  In the game, every procedure call checks the cue table: a per-segment index keeps this to a few cycles for segments without cues. A theme is read from disk a sector at a time and copied into the slot, with interrupts off for each 128-byte copy. The IORESULT the game sees is kept. With Atari800's default fast disk access this is instant; on a real drive a theme takes 1–3 s to load. A jingle plays from memory at once, over the theme, which then starts again from the top.
- **Controls.** `build.py --no-music` leaves it out; without `nes/` it is left out anyway. Converting the songs takes about 40 s, so `build/music.cache` keeps the result. The harness can record the emulator's sound (`Atari(..., sound=True)`, `save_audio`). The tests check the title theme, the castle theme after start-up, and the dungeon, fight and cemetery themes in the maze test. A lockstep run of the 3,005-key session loaded every place's theme and both battle jingles, 25 times each, with the screens still matching `pvm`.

## Testing

[`harness.py`](harness.py) drives `libatari800` from Python. It can boot the disk, type keys, read memory, decode the text screen through the display list, and take screenshots in Atari800's own NTSC palette (`palette()`; [`atari800_ntsc.json`](atari800_ntsc.json) is a copy for the picture converter).

[`demo.py`](demo.py) records a demo video (`build/demo.mp4`, about 5 minutes, with the music): the title, character creation, the tavern, Boltac's, and a maze run with two fights, spells and a treasure chest. The game scenes run in lockstep with `pvm`, which makes them repeatable. The script follows the hi-res screen's text by watching `pvm`'s `PRGRCHR`, `MVCURSOR` and `CLRRECT` calls, so a small agent can walk, fight and open the chest. `--find-seed` searches for a maze run that reaches a chest quickly. Each scene must end with the Atari's screen matching `pvm`'s, and this is how the chest and treasure pictures were first checked. The video contains the NES music, so it stays out of Git.

[`lockstep.py`](lockstep.py) runs the same key script on the Atari and on `pvm` and compares the screens after each step. Because the game's RNG depends on key timing, the test-mode build makes each key wait stir the RNG exactly as many times as `pvm` did for that key; the harness passes the count through `$05F2` before each key. The runtime sets `$05F4` while it waits for a key, so the harness types one key at a time, as a person would.

The lockstep tests (`tests/test_lockstep.py`) cover:
- character creation, with a byte-for-byte save comparison;
- the maze plus a battle, with bitmap comparison;
- the full-party adventure, whose keys are in `tests/adventure_keys.json`. They were found by driving `pvm` with a simple policy (fight with the front row, parry with the back row) and are replayed exactly.

- a 3,005-key spells-and-inn session (`tests/adventure2_keys.json`).

All four run in about 75 seconds, most of it the inn healing week by week in emulated real time.

Debug aids:
- `build.py --trace` keeps a ring of (IPC, opcode, top of stack) at `$B900`.
- Every call is logged as (segment, procedure) at `$0600`.
- Execution errors are written to `$0580`–`$0585` and shown on screen.
