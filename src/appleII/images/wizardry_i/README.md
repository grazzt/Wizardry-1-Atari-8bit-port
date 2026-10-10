# Wizardry I — Apple II disk images

Disk images are not included in this public source tree. Supply them locally under the filenames below in `src/appleII/images/wizardry_i/` before building or running tests; source URLs and hashes remain in [SOURCES.json](SOURCES.json). The findings below describe the original research copies.

Downloaded 2026-10-09 from the [Asimov mirror's Wizardry I directory](https://mirrors.apple2.org.za/ftp.apple.asimov.net/images/games/rpg/wizardry/wizardry_I/).

| Image | Purpose | Size |
| --- | --- | ---: |
| `wizardry_i_boot.dsk` | Boot disk, volume `WBV2.1` | 143,360 bytes |
| `wizardry_i_scenario.dsk` | Scenario disk, volume `WSV2.1`, **played** (20 characters on the roster) | 143,360 bytes |
| `snafaru_restored_scenario.dsk` | Scenario disk with a clean roster, restored by Snafaru ([readme](snafaru_restored_readme.txt)) | 143,360 bytes |

Thomas William Ewers's [reconstruction notes](WizardryiSource.asm.txt) name `wizardry_i_boot.dsk` as the source of the executables he reconstructed. His full source package is in [../../source/ewers_wizardry_i](../../source/ewers_wizardry_i/README.md).

The archive's [original readme](wizardry_1.readme) says to write-protect the boot disk before playing. Keep these downloads as reference copies; the emulator launchers copy them to `src/tools/emulators/state/` for sessions.

## What has been established (2026-10-09)

Checked with the project's [`ucsd` tools](../../../tools/ucsd/README.md) and [`wizardry_scenario.py`](../../../tools/wizardry_scenario.py).

- **Boot disk.** It is byte-identical to the archive's `Wizardry-Proving-Grounds-Original-Boot.dsk`. Its `WIZARDRY.CODE` is the same as the copy on the scenario disk. All 15 segments are byte-identical to Ewers's rebuilt `WIZARDRY.CODE`; only their order within the file differs.
- **Deprotected.** In `SYSTEM.STARTUP`, the WIZBOOT segment differs from Ewers's build by 51 bytes. Ewers's version still reads the Disk II data latch (`$C08C,X`) looking for the `D5 AA 96` address prologue, a copy-protection check. This image replaces that check, so it is a deprotected copy. That is expected for a `.dsk`, which cannot hold nibble-level protection, and it doesn't matter for the port.
- **Played scenario disk.** `wizardry_i_scenario.dsk` holds a played roster (JIB, DIRK THE DARING, …). Compared with `snafaru_restored_scenario.dsk`, `SCENARIO.DATA` differs only in the 20 character records, 2 bytes of maze level 6, and 1 byte of object record 62 (Boltac's stock). Those are the three items Snafaru's readme says were restored. Use the restored disk for repeatable tests that start from an empty roster. Use the played disk as save-format test data.
- **The archive's "v2.1 (san inc crack)" boot disk was not kept.** Its `WIZARDRY.CODE` and `SYSTEM.STARTUP` differ from this image, and its scenario data is a third variant.
- **Revision.** The volume names `WBV2.1`/`WSV2.1` suggest release 2.1; this has not been confirmed independently. Pascal directory dates are 1980-08-14 for `WIZARDRY.CODE`/`SYSTEM.STARTUP`, 1980-12-17 for `SYSTEM.PASCAL`, 1981-01-03 for `RTSTRP.APPLE`/`SYSTEM.LIBRARY` and 1981-08-07 for `WT`.
- **Boot test.** The boot disk and played scenario disk boot in the Apple II Plus emulator core to the animated wizard title ([screenshot](../../../test-artifacts/emulators/apple2-boot.png)). Character creation and saves have not yet been exercised in the Apple emulator; on the [host p-machine](../../../tools/pvm/README.md) they work with these images.

## The runtime: RTSTRP.APPLE

The boot disk carries its own interpreter, `RTSTRP.APPLE` ("run-time, stripped"), instead of Apple's `SYSTEM.APPLE`. These facts are from disassembling it with da65 and reading the boot blocks (2026-10-09):

- **Loading.** The boot blocks search the directory for `RTSTRP.APPLE` and read 45 pages of it to **`$9200`–`$BEFF` in main RAM**, not the language card. They then jump through the vector at `$BEFE` to `$B69E`. The file's last 3 pages (from offset `$2E00`, containing the text `THISISIT`) are not loaded.
- **Initialisation.** It clears `$0000`–`$91FF` and page `$BF`. It scans slots 7–1 for Pascal-protocol firmware cards. It installs the keyboard poll CONCK at `$BF0A` (`JSR $BD90 / RTS`), which the game's KEYAVAIL and MVCURSOR call, and sets the display soft switches. The first page holds the `SYSTEM.PASCAL` file name and its "not found" message.
- **Opcode dispatch.** The table is at `$9600`: 128 entries for opcodes 128–255. The standard-procedure (CSP) table follows at `$9700`.
- **What was stripped.** 18 opcodes and 12 standard procedures go to a handler at `$97EF` that raises execution error 11 (unimplemented instruction):
  - all REAL arithmetic (ABR ADR DVR MPR NGR SBR SQR FLO FLT);
  - all SET operations (DIF INN INT SRS SGS UNI ADJ);
  - EFJ and NFJ;
  - IDSEARCH, TREESEARCH, TRUNC, ROUND, the transcendental functions and PWROFTEN.

  Every opcode used by `WIZARDRY.CODE`, `SYSTEM.STARTUP` and `SYSTEM.PASCAL` is among the 110 that remain. That independently confirms the project's opcode table.
- **`NIL` is 0.** `LDCN` pushes zero.
- **Zero page.** The interpreter uses most of `$50`–`$FF`, and the game's native routines use `$00`–`$2A`.

The [host p-machine](../../../tools/pvm/README.md) implements exactly this subset.

Source URLs and SHA-256 hashes are in [SOURCES.json](SOURCES.json); after supplying the external files, run `sha256sum -c SHA256SUMS` from this directory to verify the files.
