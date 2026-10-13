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

## Two-disk release

The current download is a **two-disk build with PCE monster pictures and gameplay music**. Disk 1 contains the program and title; Disk 2 contains the game, scenario, 95 picture records, 11 gameplay themes and four jingles. Both fit the 180 KB capacity budget. The title and options are silent; music begins at the castle. Loading preserves the display while compressed data is decoded.

**It should now be playable on real 64 KB Atari XL/XE hardware with a compatible writable ATR-capable SIO device.** Physical Atari operation remains unverified. These images use 128-byte logical sectors (467 on Disk 1, 1,440 on Disk 2), so physical-floppy compatibility depends on your drive and conversion tools. Emulated boot, swaps and saves pass with Atari800's fast SIO patch disabled.

See the [project README](../README.md) for the downloads, Windows Atari800 command, disk swaps, saves and Recover. Keep Disk 2 writable and play on a copy; it holds your characters and progress. The optional party pair starts with six powerful characters already formed, ready for **E)dge → M)aze → L)eave camp**. The older single-image build remains available too.

The [validation log](test-artifacts/two-disk/tests.log) records all 50 Atari tests passing. A full playthrough and PAL operation remain unverified. Utilities other than Recover remain untested; Make scenario disk and Update need another drive and are unsupported.

## Build from source

Start in the GitHub repository's root and enter `src/` as shown below. Run subsequent build and test commands from `src/` unless a command explicitly changes directories. The setup scripts target Linux/WSL. Use Python 3.10 or newer, `git`, `curl`, GCC, Make and `unzip`.

External build-input disk images are **not included** in this source tree. Ready-to-play ATRs are available at the repository root. Before building, supply these files locally:

- `appleII/images/wizardry_i/wizardry_i_boot.dsk`
- `appleII/images/wizardry_i/snafaru_restored_scenario.dsk`

The regression tests and demo also use `appleII/images/wizardry_i/wizardry_i_scenario.dsk` (the played scenario). UCSD tests additionally need the five Ewers source/build disks at the paths recorded in [the source manifest](appleII/source/ewers_wizardry_i/SOURCES.json). Original source URLs and expected hashes are preserved in [the game disk manifest](appleII/images/wizardry_i/SOURCES.json). These files remain ignored by Git when supplied locally.

```bash
cd src
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
tools/toolchain/setup.sh
python3 port/atari/build.py --disk2
```

The build uses ca65/ld65 from the local toolchain and the Apple II disks supplied locally as described above. It works without the optional music and replacement artwork. The Python dependencies are NumPy and Pillow, used by the picture converter. The first compressed build compiles the vendored [ZX02 compressor](tools/zx02/README.md) with `cc`.

For the illustrated monster pictures, fetch the optional assets before building:

```bash
python3 port/atari/pictures.py --fetch
python3 port/atari/build.py --disk2 --pictures monster
```

For music, supply the NES version's NSF at `nes/snafaru/wiz1.nsf` before building. Downloaded artwork, NES music, converted caches and build outputs are ignored by Git. See the [picture and music documentation](port/atari/README.md#pictures) for details and credits.

To rebuild while preserving a party saved on an earlier ATR:

```bash
python3 port/atari/build.py --disk2 --pictures monster --scenario /path/to/saved_disk2.atr
```

The new pair is written to `port/atari/build/wizardry_disk1.atr` and `wizardry_disk2.atr`; back up the old play disk first. An older single-image ATR can also be imported with `--scenario`.

For the preformed level-50 party:

```bash
python3 port/atari/build.py --disk2 --pictures monster --party --out wizardry_party.atr
```

This writes `wizardry_party_disk1.atr` and `wizardry_party_disk2.atr` in the build directory. Existing occupied roster slots are preserved. All six seeded characters must still be alive and in town for automatic formation at startup; it uses their saved stats. See [party details](port/atari/README.md#two-disk-build-with-pce-pictures).

Omit `--disk2` to produce the older single-image format, including title music when the NSF is installed.

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
python3 port/atari/build.py --disk2 --test-images
python3 port/atari/build.py --disk2 --pictures monster --testmode --out test_pce.atr
python3 port/atari/build.py --disk2 --pictures monster --testmode --no-title --scenario appleII/images/wizardry_i/wizardry_i_scenario.dsk --out played_pce.atr
python3 port/atari/build.py --disk2 --party --pictures monster --testmode --no-title --out test_party.atr
python3 -m unittest discover -s port/atari/tests -t port/atari
```

The complete 50-test run needs the optional sprites and NSF as well as the disk fixtures. Tests for absent fixture builds are skipped. The tests compare the Atari runtime against the host p-machine, including screens and saved scenario bytes. Demo recording additionally requires FFmpeg; see [the Atari testing notes](port/atari/README.md#testing).

## Source directory guide

All paths below are inside the repository’s `src/` directory. For example, the built disks are under `src/port/atari/build/` when addressed from the repository root.

| Path | Contents |
| --- | --- |
| [port/atari](port/atari/README.md) | Atari assembly runtime, build and asset converters, emulator harness, lockstep tests and screenshots |
| [tools/ucsd](tools/ucsd/README.md) | Apple Pascal disk reader, code-file parser, p-code and 6502 analysis |
| [tools/pvm](tools/pvm/README.md) | Host reference p-machine and regression tests |
| [tools/wizardry_scenario.py](tools/wizardry_scenario.py) | Scenario tables, roster inspection and record comparisons |
| [tools/zx02](tools/zx02/README.md) | Vendored lossless compressor and upstream licences |
| [tools/nes/nsf.py](tools/nes/nsf.py) | NSF playback and music analysis utility |
| [tools/toolchain](tools/toolchain/README.md) | Reproducible local cc65 and CiderPress II setup |
| [tools/emulators](tools/emulators/README.md) | Emulator setup, launchers and optional MCP configuration |
| [appleII](appleII/README.md) | Apple II references, external disk manifests, reconstructed Pascal/assembly listings and provenance |
| [atari](atari/README.md), [c64](c64/README.md), [common](common/README.md) | Platform manuals, format references and shared 6502/cc65 documentation |
| [SPEC.md](SPEC.md) | Port design and fidelity requirements |
| [RESEARCH.md](RESEARCH.md) | Research catalog, findings and reference-library instructions |
| [test-artifacts/emulators](test-artifacts/emulators) | Reference emulator screenshots and recorded protocol checks |

External disk fixtures, PDF books and the two C64 book transcriptions are omitted from this source tree. The book transcriptions remain catalogued for provenance but are not fetched by the reference helper. Large reference PDFs are optional local downloads. Restore them with `python3 tools/fetch_refs.py`; source URLs and checksums are recorded in each library's `SOURCES.json` and `SHA256SUMS`. They are optional for building the game. Local tool installations, working save disks and personal session settings are excluded.

## Credits

Original Wizardry by Andrew Greenberg and Robert Woodhead / Sir-Tech. Pascal and assembly reconstruction by Thomas William Ewers; restored scenario by Snafaru. Music from the NES version by Kentaro Haneda. Monster artwork uses Jun Suemi's designs as depicted in the PC Engine version. ZX02 compression by Daniel Serpell; upstream licences are included in `tools/zx02/`.

Wizardry and the original game, music and artwork belong to their respective rights holders. This is an unofficial fan port.
