# Wizardry I — Commodore 64 disk images

Disk images are not included in this public source tree. Supply them locally under the filenames below in `src/c64/images/wizardry_i/` to use the C64 emulator launcher; source URLs and hashes remain in [SOURCES.json](SOURCES.json). The findings below describe the original research copies.

Downloaded 2026-10-09 from the [Internet Archive's Wizardry I C64 item](https://archive.org/details/d64_Wizardry_I_Proving_Grounds_of_the_Mad_Overlord_1982_Sir-Tech_Side_A).

| Image | Archive designation | Disk label | Size |
| --- | --- | --- | ---: |
| `wizardry_i_side_a.d64` | Side A; emulator startup image | C64WIZMASTER | 174,848 bytes |
| `wizardry_i_side_b.d64` | Side B | WIZARDRY | 174,848 bytes |

Both images come from the same archive item. Their long upstream filenames were shortened locally; the bytes are unchanged. The original filenames and URLs are recorded in [SOURCES.json](SOURCES.json), and the complete [archive metadata](archive_metadata.json) is retained.

The archive filename contains “1982”, while its embedded release metadata also gives “1987”; do not use that filename alone to establish the C64 release date or game revision. Whether the images contain historical cracks or other modifications has not been established. The archive's file-level `source: original` field identifies an uploaded file, not proof of an unmodified retail disk.

Validation: both images have standard 35-track D64 size, recognizable disk labels and Wizardry content, and match the archive's published MD5 and SHA-1 digests. Local SHA-256 hashes are also saved. On 2026-10-09 side A booted in VICE `x64sc` to the disk-A prompt ([screenshot](../../../test-artifacts/emulators/c64-boot.png)); disk swaps and gameplay have not yet been exercised.

Start with side A and switch images when prompted. Use copies for emulator sessions so character creation and saves do not alter these reference downloads. Run `sha256sum -c SHA256SUMS` from this directory to verify the saved files.
