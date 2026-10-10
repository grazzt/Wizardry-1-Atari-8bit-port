# Installed emulators

Installed 2026-10-09 under this directory, using about 280 MB. The installation (`downloads/`, `src/`, `local/`) is ignored by Git. **After cloning, rebuild it with `./tools/emulators/setup.sh`**; see [Rebuilding](#rebuilding). The source package lives under the GitHub repository’s `src/` directory. Run `cd src` from the repository root before the setup command above, then run the commands below from `src/` in a **normal WSL terminal**. VICE and Atari800 need WSLg or another working X display. Apple runs in a browser.

| System | Installed | Automation |
| --- | --- | --- |
| C64 | [VICE](https://vice-emu.sourceforge.io/) 3.7.1, `x64sc`, Ubuntu amd64 package | [simen/vice-mcp](https://github.com/simen/vice-mcp) 1.0.1; 26 tools |
| Apple II | [web-a2e / ApplEm](https://github.com/mikedaley/web-a2e) deployed build 1.8.3, saved locally | [appleii-agent](https://github.com/mikedaley/appleii-agent) 1.3.0; 16 tools |
| Atari 8-bit | [Atari800](https://github.com/atari800/atari800) 7.2.1, built with SDL2 | Built-in monitor; no Atari MCP installed |

## Launch

```bash
./tools/emulators/bin/c64
./tools/emulators/bin/atari800
./tools/emulators/bin/apple2
```

Run each in its own terminal. The C64 launcher autostarts side A, enables true 1541 drive emulation, and opens the binary monitor on `127.0.0.1:6502`. Its initial game prompt asks for disk A; press Return with side A attached. Attach side B to device 8 when requested, using the working copy below.

Atari starts as a 65XE equivalent (800XL, 64 KB; the port's target), NTSC, BASIC disabled, with the bundled Altirra replacement OS. Pass `-xe` for a 130XE. The keyboard joysticks (WASD and the numeric keypad by default) are disabled, because they swallow those keys when typing names; Wizardry has no joystick control. Its settings are in [config/atari800.cfg](config/atari800.cfg), which the launcher reads but never rewrites. This validates the development environment, not an Atari Wizardry port. Pass an ATR filename to mount a future build. Press F1 for emulator controls and F8 for its monitor.

The Apple command serves the local emulator at **http://127.0.0.1:8088** and prints a link that loads the boot and scenario images into drives 1 and 2. Open that printed link, select **Apple II Plus** (with language card), and reset if necessary. Enable write protection for the boot disk in the disk controls. Stop the server with Ctrl-C. The saved snapshot includes the emulator assets; optional online disk-library titles were not downloaded.

The launchers copy originals into `state/c64-disks/` and `state/appleII-disks/` only when absent. The Apple link loads the played scenario disk; to start with an empty roster, copy `snafaru_restored_scenario.dsk` over `state/appleII-disks/wizardry_i_scenario.dsk`. Use these copies for disk swaps and saves. Browser changes remain in the emulator until exported; export saves explicitly. To start fresh, stop the emulator, retain any wanted saves, and remove the corresponding working copy before relaunching.

## MCP in Claude Code

The project's [.mcp.json](../../.mcp.json) registers both servers as `wizardry_vice` and `wizardry_apple2`. Claude Code asks you to approve project MCP servers the first time it starts in this directory. The commands are relative paths, so start Claude Code from the repository’s `src/` directory. Connecting each server to its emulator works as described for Codex below.

## MCP in Codex

```bash
./tools/emulators/bin/codex-retro
```

This starts a **new Codex session** with both MCP servers configured through command-line overrides. It preserves existing settings. It does not register tools in the already-running session. The equivalent configuration is in [config/codex-mcp.toml](config/codex-mcp.toml); replace its `/path/to/wizardry_1` placeholder with the absolute path to the repository’s `src/` directory (for example, `/path/to/repository/src`) and merge it into a normal Codex configuration if permanent registration is wanted. Codex supports these overrides and server settings in its [MCP documentation](https://developers.openai.com/codex/mcp/).

For C64, launch `bin/c64`, then ask Codex to connect the VICE MCP server to `127.0.0.1:6502`. Its tools inspect registers and memory, set breakpoints, step execution and capture the screen.

For Apple, launch `bin/apple2` and open the browser link. Enable the agent connection using the emulator's sparkle/agent toolbar control, pointing at `http://localhost:3033`. The MCP process supplies that HTTP bridge. Disk paths use `[disks]/wizardry_i_boot.dsk` and `[disks]/wizardry_i_scenario.dsk`; `[output]/` maps to `test-artifacts/emulators/`. Run only one Apple MCP instance on port 3033. A one-line local patch binds its HTTP listener to `127.0.0.1`; see [config/appleii-loopback.patch](config/appleii-loopback.patch).

No live Atari MCP integration has been established. Atari800's monitor is sufficient to start the port; a scripted libatari800 harness can be added when there is Atari code to exercise. AtariHackerMCP was not installed: its static disk/disassembly functions do not provide live emulator control.

## Rebuilding

```bash
./tools/emulators/setup.sh                            # emulators and MCP servers
./tools/emulators/setup.sh --with-reference-sources   # also clone web-a2e and applem-core sources
```

It also builds `local/lib/libatari800.so`, Atari800 as a library, which the Atari port's test harness drives. The script reads pinned versions, URLs, commits and hashes from [SOURCES.json](SOURCES.json). It downloads and verifies the VICE package and ROMs, builds Atari800 with SDL2, downloads the web-a2e snapshot file by file, clones the MCP servers at their pinned commits, applies the loopback patch, installs locked npm archives without lifecycle scripts, and builds vice-mcp. Completed steps are skipped, so it is safe to re-run. It needs `curl`, `git`, `python3`, `node`, `gcc`/`make`, `dpkg-deb`, SDL2 development headers, and GTK3 runtime libraries for VICE.

At the end it checks [SHA256SUMS](SHA256SUMS). Downloads must match exactly. `local/bin/atari800` is expected to differ when built under a different path, because the install prefix is compiled in. If the web-a2e site has been redeployed, its files will no longer match and the script stops; the saved snapshot can't be re-downloaded in that case.

## Verified and remaining checks

- **Clean rebuild (2026-10-09):** `setup.sh` was run in an empty copy of this directory. It finished in 44 seconds, and a second run took 0.4 seconds. All downloads and the vice-mcp build matched SHA256SUMS. The rebuilt C64 reached the same disk-A prompt, Atari800 ran headless, and `check_mcp.py` passed for both servers.

- C64 executed 120 million cycles with the supplied disk and reached the disk-A prompt: [screenshot](../../test-artifacts/emulators/c64-boot.png). VICE intentionally exits with status 1 when `-limitcycles` is reached.
- Apple II Plus WebAssembly core loaded both disks and executed 120 million cycles, reaching the animated wizard: [screenshot](../../test-artifacts/emulators/apple2-boot.png). This tested the actual saved core under Node, not the browser UI.
- Atari800 initialized SDL with dummy video/audio and ran until a three-second timeout. Its config confirms 128 KB, NTSC and replacement OS.
- Both MCP servers passed initialize, tool listing and a status call: [results](../../test-artifacts/emulators/mcp-protocol.json). Repeat with `python3 tools/emulators/check_mcp.py`. The Apple check uses its real MCP class with the HTTP listener unstarted.
- **Not yet verified:** desktop/browser interaction, live MCP-to-emulator connections, disk swaps, character creation, and save/reload. The installation session prohibits sockets and desktop access. Its sudo access is also disabled, so everything was installed inside the project and no global Codex config was changed.

For a bounded C64 check without MCP or a display:

```bash
./tools/emulators/bin/c64 --headless --no-mcp -warp -limitcycles 120000000 \
  -exitscreenshot "$PWD/test-artifacts/emulators/c64-boot.png"
```

Installed tools rely on this machine's Python 3, Node, GTK3 and SDL2 libraries. The download/source/build directories are retained; [SOURCES.json](SOURCES.json) records versions, source revisions and checksums. The Apple runtime is a downloaded deployment snapshot, not a build of the separately checked-out source tree. Locked npm dependencies were integrity-checked and extracted without lifecycle scripts using `install_node_locked.py`; VICE MCP was then built with its local build tools. Generated installations, caches and working disks are ignored by Git.
