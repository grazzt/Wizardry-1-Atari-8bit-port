# `pvm` — host-side p-machine for Wizardry I

`pvm` runs the real `WIZARDRY.CODE` from the Apple boot disk on a PC. It gives the port a fast, scriptable reference: the same inputs and seed always produce the same memory, screens and scenario-disk writes.

From the GitHub repository root, enter `src/tools` to run these examples. Other package paths in this guide are relative to `src/`.

```bash
cd src/tools
python3 -m pvm --keys '\r\r'                          # boot to the castle and print the screen
python3 -m pvm --keys '\r\rET' --png out.png          # also render the hi-res page
python3 -m pvm --keys '...' --trace calls.txt         # log every procedure call by name
python3 -m pvm --keys '...' --save-scenario saved.dsk # keep the scenario disk with any saves
python3 -m unittest discover -s pvm/tests -t .        # end-to-end tests (about 3 s)
```

Keys use Python escapes (`\r` is RETURN, `\x1b` is ESC). A run stops when the keys run out, the program ends, or `--max` instructions have executed. It then prints the 40×24 text screen, the display mode, the loaded segments and memory statistics. The default scenario disk is `snafaru_restored_scenario.dsk`, which has an empty roster. From Python, `PMachine.send(keys)` types keys and runs until the game wants more input; see `tests/test_pvm.py`.

## What works (2026-10-09)

The tests script all of this:

- **Start-up.** Scenario lookup, table-of-contents load and character set.
- **Castle and town.** The castle, Gilgamesh's Tavern, the Edge of Town and the Training Grounds.
- **Character creation.** Including bonus-point allocation and class choice. It is saved to the scenario disk when leaving the game, read back by [`wizardry_scenario.py`](../wizardry_scenario.py), and reloaded into a party.
- **The maze.** Entering the maze through camp, the 3D view, movement, walls and the stairs prompt.
- **Combat.** Encounter, monster picture, options, melee rounds with hits, damage and kills, death, and the cemetery.

Throughput is about 500,000 p-code instructions per second. A full battle takes a few seconds.

## How it works

| Part | Implementation |
| --- | --- |
| p-code | All 110 opcodes implemented by the game's runtime (see [RTSTRP.APPLE](../../appleII/images/wizardry_i/README.md#the-runtime-rtstrpapple)); decoding comes from [`ucsd`](../ucsd/README.md) |
| Memory | One 64K byte array. Frames, code segments and the heap live in it, so pointers, `UNITREAD` into arrays and the game's absolute addresses (`$2000`, `$4000`, `$0479`) behave as on the Apple. |
| Segments | Loaded onto the stack at the first call and released when their last activation returns, as on the real machine. This is what makes the memory measurements meaningful. |
| Native routines | The game's own 6502 code runs in [`cpu6502.py`](cpu6502.py) on the same memory, after the real relocation fix-ups. The evaluation stack is copied to and from the 6502 stack, which is the same thing on the Apple. Graphics land in hi-res memory and are rendered to PNG. |
| BIOS | The keyboard poll (`JSR $BF0A`) is a host trap. Reads of `$C000` deliver scripted keys, and display soft switches are tracked. |
| Pascal OS | Not run. The OS entry points the game calls (WRITE char/string/integer, WRITELN, READ, READLN, EOLN, GOTOXY, CONCAT, COPY) and the standard procedures are Python. Console units 1/2 read keys; units 4/5 are the scenario and boot disks. |

Frame conventions were established from the code, not assumed. Arguments are pushed in order, and a function's two result words are pushed last, so local word 1 is the last word pushed and `RNP n` returns words 1..n. `EXIT` makes every activation up to the named one run its exit code.

### Randomness and key timing

The game's RNG lives in Apple text-page "screen holes" (`$047A`, `$04FA`, `$057A`, `$05FB`). It is stirred by `MVCURSOR(80)`, which loops incrementing `$047A` until a key arrives, so on real hardware human timing seeds the game. Here, each key is reported after a number of polls drawn from `random.Random(--seed)`. A given seed and key script therefore reproduce the same game exactly.

### Start-up: `--title`

With `--title` (or `startup=` in Python), the machine runs `SYSTEM.STARTUP` first: the title animation, then the copyright and options screen. Drive 1 is the boot disk, write-protected as the program checks. It provides:
- the Pascal file operations it uses (`FINIT`, `FOPEN`, `FBLOCKIO`, `FCLOSE`);
- the `CHAINSTUFF` unit's `SETCHAIN`;
- p-code reads of `$C000` (through the key-timing model) and soft-switch writes.

S)tart ends the program, and the machine chains to `WIZARDRY.CODE`, with the scenario disk now as drive 1.

### Input that runs out

`send(keys)` may be called with one key at a time. If the keys run out inside a call (a native routine waiting for a key, or an OS READ), the instruction is undone and rerun when more keys arrive. `MVCURSOR(80)` checks for a key before stirring, so splitting a script into single keys gives exactly the same result as sending it whole; a test checks this. `poll_log` records the number of polls used for each key, which the Atari lockstep harness replays.

### Departures from the Apple

- **Copy protection is patched out** with the byte patches in [`patches.py`](patches.py), which the Atari build shares. `SPECIALS.16` (COPYPROT) times disk nibbles with 6502 code it loads at `$2000`, which a host cannot do; it is replaced by p-code that stores 10 at `$0479`, the marker a successful check leaves, which CASTLE tests before `MVCURSOR(70)` ("crash and burn"). In `SYSTEM.STARTUP`, `CHKCOPY` keeps reading the serial number and skips its timing loop. `GTSERIAL` and the master/duplicate serial check still run.
- **A divide by zero is patched out of the rewards code.** `REWARDS.27` (`CALCULAT`) evaluated `RANDOM MOD AVEAMT` with `AVEAMT = RANGE = 0` for the fixed item drops (reward records 20 and 21), which ended the game with execution error 6 after the Werdna fight. The second patch in [`patches.py`](patches.py) makes it return 0 when `AVEAMT <= 0`, so the drop is `MININDX` itself (item 94, Werdna's Amulet); positive ranges roll as before. `CalculatTests` in `tests/test_pvm.py` cover it, and the Atari lockstep test `test_werdna_fight_gives_the_amulet_without_error` replays the whole fight on both machines.
- **The console is a model.** Apple Pascal control codes 7, 8, 10–13, 25, 28, 29 and 31 are handled. The cursor may sit past column 39, where output is dropped; Wizardry parks it at column 41 to hide key echoes. Field-width rules for WRITE(string) follow standard Pascal and haven't been compared with the Apple.
- **Uninitialised memory.** Memory starts zeroed. The Apple interpreter also clears `$0000`–`$91FF` at boot, but later garbage will differ.
- **Memory layout is assumed.** The stack top is `$9200`, where `RTSTRP.APPLE` begins, and the heap starts at `$4000`, which is what the game sets. A 12-byte mark-stack word is counted per frame. The real interpreter's exact layout below `$9200` has not been traced.

## Memory measured so far

The peak stack use is **15,798 bytes**, reached in combat. It breaks down as:

| Item | Bytes |
| --- | ---: |
| Code: WIZARDRY (resident) | 3,410 |
| Code: COMBAT | 50 |
| Code: CUTIL | 7,014 |
| Program globals | 3,438 |
| COMBAT frame | 1,490 |
| Other frames and mark-stack words | Small remainder |

No heap is allocated (the game never calls NEW), so least free memory was 5,194 bytes between `$4000` and the stack. A longer 313-key session with a six-character party (spell books in `UTILITIE`, shops, the inn, a camp spell, a won battle with `REWARDS`) peaked at the same 15,798 bytes. Combat spells (`CASTASPE`), chests and levelling up have not been measured yet.

## Not yet done

- **Wider coverage:** spells, shops, levelling, traps, chests and the ending. Each new path may exercise semantics that haven't been tested yet.
- **Comparison with the Apple emulator** on identical inputs. The key-timing model makes the RNG differ from a human-played Apple, so comparisons need matching seeds or matching RNG states.
- **`SYSTEM.STARTUP`'s U)tilities.** Backup, recover and transfer are untested.
