# Wizardry I → Atari 8-bit

Proposed approach · 2026-10-09 · Port feasibility remains untested; source analysis is under way (see [Status and next steps](#status-and-next-steps)). [Emulator installations and initial checks](tools/emulators/README.md) are complete; live MCP connections remain untested.

## Recommendation

**Use the Apple II release as the source. First attempt to adapt its Pascal runtime and replace machine-dependent routines, preserving game logic and data.** Use the C64 version as a comparison reference.

The strongest advantage is the existing Pascal/assembly reconstruction: [Ewers's notes](appleII/images/wizardry_i/WizardryiSource.asm.txt) identify our Apple boot image and claim reproducible executables. His [listings now check out against our files](appleII/source/ewers_wizardry_i/README.md); an actual Apple Pascal 1.1 rebuild remains to be done. The newer [Wizardry.Code](https://github.com/snafaru/Wizardry.Code) modifies gameplay; consult it without adopting its changes as the baseline.

## Initial target

- **Atari 65XE (64 KB, XL/XE OS, no extended memory)**, keyboard, BASIC disabled. This is the owner's machine and the first target; Atari800 emulates it as `-xl`. The fallback is the 130XE (128 KB) if 64 KB proves too tight. Measured needs so far (15.8 KB peak p-machine stack, no heap) suggest 64 KB is comfortable.
- Bootable ATR disk set and separate writable save disk; standard SIO, initially 90KiB single-density images compatible with 810/1050 drives. Allow multiple disks.
- Monochrome 320×192 bitmap, retaining the original 280-pixel-wide layout where practical. Preserve text, dungeon geometry and gameplay before enhancing presentation.
- Ordinary emulation speed; NTSC first, PAL before completion. No cartridge or graphics expansion required.

## Fidelity: what must match and what may differ

The port is faithful in **behaviour**, not a pixel-for-pixel or sample-for-sample copy.

- **Must match exactly:**
  - game logic, including the random-number generator and its seeding;
  - game data, messages and menus;
  - the save format (`SCENARIO.DATA`).

  The host p-machine checks these, and a character or scenario disk should mean the same thing on both machines.
- **May differ if it looks similar:**
  - colours (the Apple's hi-res artifact colours can become whatever the Atari displays well; monochrome is acceptable);
  - pictures: the monster pictures may be redrawn, as long as the game runs unchanged. The port shows Jun Suemi's monsters from the PC Engine version, one per monster (see the Atari README). That shows what a monster is before the party has identified it, which the Apple's 20 shared pictures did not; `build.py --pictures class` keeps the Apple's behaviour.
  - sound: music the Apple never had may be added, as long as it never affects the game. The port plays the NES version's music: the title theme, each place's theme and the jingles (see the Atari README).
  - pixel aspect and screen position;
  - font rendering;
  - small layout adjustments forced by the Atari screen.

  Keep the 3D maze view, monster pictures and screen arrangement recognisable.
- **Sound is optional.** The Apple version appears to have no music. Its native routines never touch the speaker, and the runtime reaches `$C030` in a single place, consistent with the console bell (`CHR(7)`). An Atari beep or keyclick is enough. If memory runs short, sound is the first thing to drop.

## Emulators and MCP

**Use MCP where it saves work; make repeatable scripts the foundation.** Apple and C64 images reach initial boot screens; disk swaps, gameplay and live MCP compatibility remain to be verified.

| Role | Selection | MCP decision |
| --- | --- | --- |
| Apple reference | [web-a2e](https://github.com/mikedaley/web-a2e), II Plus + language card | Evaluate its advertised Apple II agent/MCP integration. Require boot, disk swap, memory inspection and repeatable input to work before adopting it. |
| Atari development | [Atari800 / libatari800](https://github.com/atari800/atari800/blob/master/DOC/README) on Linux | Build a small scripted harness around its frame, memory and framebuffer access. Add MCP only if useful for interactive debugging. |
| Atari cross-check | [Altirra](https://www.virtualdub.org/altirra.html); [AltirraSDL](https://github.com/ilmenit/AltirraSDL) is an unofficial Linux option | Use for independent emulator checks and debugging; no live MCP integration verified. |
| C64 comparison | VICE `x64sc` + [simen/vice-mcp](https://github.com/simen/vice-mcp) | Existing wrapper over VICE's binary monitor. Optional; inspect behavior when the Apple implementation is unclear. |
| Atari static analysis | [AtariHackerMCP](https://github.com/pdavis68/AtariHackerMCP) | Available for ATRs/disassembly; its documented interface is static analysis, not live emulator control. Optional. |

Pin tool revisions after smoke tests. Record ROM hashes and machine settings. If Apple MCP integration stalls, use a conventional Apple emulator/debugger and disk extraction; the source choice does not depend on MCP. Avoid developing three emulator integrations before proving the port.

## Implementation strategy

1. Extract Pascal files, segment dictionaries, native routines and game data with [CiderPress II](tools/toolchain/README.md) or the project's [`ucsd` tools](tools/ucsd/README.md). Decode p-code separately from 6502 instructions. *(Done for code: both tools are installed, and `ucsd` decodes every procedure, verified against Ewers's listings.)*
2. Audit the **actual game interpreter** against the saved Pascal disassembly. Retarget its memory references and native-call conventions; preserve p-code semantics and overlay loading.
3. Implement Atari adapters for text/bitmap drawing, keyboard input, disk blocks, timing, sound and randomness. Preserve the game's RNG behavior; add controlled seeds for comparisons.
4. Assemble native code with [ca65/ld65](common/tools/ca65.html); use Python for extraction and ATR construction. Keep recovered Pascal as the readable reference; reproduce the Apple Pascal 1.1 build when recompilation is needed.

**Main risk: memory layout.** Budget interpreter, p-code stack/heap, largest overlay, screen, buffers, OS workspace and interrupts. XE banking provides storage, not a flat 128KB address space. Resolve zero-page conflicts, the Atari I/O region, ROM banking and SIO access explicitly. Do not assume Apple binaries relocate unchanged.

## Milestones and exit criteria

| Step | Required result |
| --- | --- |
| 1. Establish baseline | Boot working copies of both source sets; identify revisions. Download Ewers's reconstruction, compare/rebuild executables, and record any differences. Capture Apple character creation, maze entry and save/reload. |
| 2. Prove feasibility | Produce a memory map and native-interface inventory. On Atari, execute representative p-code calls, load an overlay from ATR, draw text and accept input. Measure memory high-water marks and normal-speed execution. |
| 3. First playable slice | Create a character → enter the maze → move → complete one battle → return → save → reboot and reload. |
| 4. Complete and verify | All ten levels, spells, shops, character states and ending work. Test disk swaps, full/write-protected saves, PAL/NTSC and a second emulator; check real hardware when available. |

**Decision after step 2:** continue runtime adaptation only if memory, relocation and speed are tractable. Otherwise translate recovered Pascal incrementally into cc65 C with assembly for critical routines, retaining the same data and comparison tests.

## Verification and deliverables

Keep downloaded images immutable; run disposable copies. Compare Apple and Atari at logical checkpoints using identical inputs and controlled RNG: party statistics, combat outcomes, coordinates, inventory and save records. Check screen layout separately; cross-platform screenshots need not match pixel-for-pixel.

Deliver reproducible extraction/build commands, documented source hashes, native adapters/runtime, ATRs, and saved regression scenarios. **First deliverable is the feasibility report and Atari runtime demonstration—not the entire game.**

## Status and next steps

**Done (2026-10-09):**

- **Repository.** PDFs moved out of Git and restored by `tools/fetch_refs.py`; shared docs moved to `common/`.
- **Setup scripts.** `tools/emulators/setup.sh` and `tools/toolchain/setup.sh` rebuild everything from pins; a clean emulator rebuild was tested. Project `.mcp.json` added.
- **Ewers sources.** Downloaded and verified against our binaries. Disk provenance is resolved.
- **Analysis tools.** `tools/ucsd` covers p-code and code files; `tools/wizardry_scenario.py` reads scenario data.
- **`RTSTRP.APPLE` identified** ([notes](appleII/images/wizardry_i/README.md#the-runtime-rtstrpapple)):
  - It loads at `$9200`–`$BEFF` in main RAM.
  - Its dispatch table is at `$9600`.
  - 110 opcodes remain; REALs, SETs, EFJ/NFJ and 12 standard procedures are stripped.
  - Every opcode the game uses is implemented.
- **Host p-machine working** ([`tools/pvm`](tools/pvm/README.md)). It runs the real `WIZARDRY.CODE`, with the native routines running in a 6502 emulator. It covers boot, the castle, character creation, saving and reloading, party formation, maze entry and movement, and a complete battle through to the cemetery. Runs are deterministic for a given seed and key script, and end-to-end tests check it.

**Measurements that affect the plan:**

- **Peak stack use so far is 15,798 bytes** (in combat). That is 10,474 bytes of loaded code, 3,438 bytes of game globals, and frames.
- **The game allocates no heap.** Its fixed memory beyond the stack is the hi-res page (8 KB, also the copy-protection load area at `$2000`) and its use of text-page screen holes.
- **A small runtime looks sufficient.** Supporting the game needs:
  - 110 opcodes, none of them REAL or SET operations;
  - 9 standard procedures;
  - about 10 OS entry points;
  - console and block I/O;
  - seven native routines.

  This makes a 64 KB XL/XE target, and possibly 48 KB, look feasible, before any banking.
- **The RNG is seeded by key timing.** It is stirred while waiting for keys, so comparisons need a controlled key-timing model on both sides. `pvm` already has one.

**Next steps, in order:**

1. **Widen host coverage.** Script spells (CASTASPE), shops, levelling, treasure, traps and saving after a won battle. Record peak memory for each, especially paths that load UTILITIE (7,766 bytes).
2. **Compare against the Apple emulator** on the same scenario disk. Use matching inputs and patch the RNG state at a checkpoint so both sides start equal. Compare screens and saved character records. This turns `pvm` into a trusted oracle.
3. **Build the Atari runtime spike (Milestone 2).** *Largely done: [port/atari](port/atari/README.md) runs the original `WIZARDRY.CODE` on a 65XE in 6.2 KB of 6502 code. In lockstep with `pvm` it matches every screen and bitmap through character creation and saving, the maze, an encounter and a battle. `SYSTEM.STARTUP` also runs: the title in colour (ANTIC mode E, within the fidelity rules; the monster pictures are redrawn in colour from the PC Engine version's sprites, with players and missiles for the colour) and the options screen, and U)tilities R)ecover, with the utilities' disk swaps done on the one disk. Remaining: wider coverage, then Milestone 3's "win, return, save, reload" slice and real-hardware checks.* Write a ca65 p-machine implementing the 110 opcodes, then console, keyboard and SIO block I/O. Rewrite the seven natives for Atari graphics. Show it reaching the castle screen in Atari800, with `pvm` as the reference for every step.
4. **Optionally rebuild with Apple Pascal 1.1.** This is a confirmation step only.
