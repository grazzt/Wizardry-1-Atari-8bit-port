# Ewers's reconstructed Wizardry I source

The Pascal and assembly text listings are included; the five `.DSK` source/build disks are not. Supply those disks locally at the paths in [SOURCES.json](SOURCES.json) before running UCSD regression tests or the disk-extraction examples below. Checksums are retained for those external files.

Thomas William Ewers reconstructed Pascal and 6502 assembler source for Wizardry I's `WIZARDRY.CODE` and `SYSTEM.STARTUP` (March–June 2014). He states that compiling it with Apple Pascal 1.1 reproduces the original executables exactly. His notes are in [WizardryiSource.asm.txt](../../images/wizardry_i/WizardryiSource.asm.txt). The names and structure are his reconstruction, not Sir-Tech's original source.

| Path | Contents |
| --- | --- |
| [WizardryCode/Wiz1WizardryPascal.txt](WizardryCode/Wiz1WizardryPascal.txt) | Compiler listing of `WIZARDRY.CODE`: line, segment, procedure, nesting level and code offset for every statement |
| [WizardryCode/Wiz1WizardryAssembler.txt](WizardryCode/Wiz1WizardryAssembler.txt) | Assembler listings of the 7 native routines (CLRPICT, DRAWLINE, RANDOM, KEYAVAIL, CLRRECT, MVCURSOR, PRGRCHR) |
| `WizardryCode/Wiz1A–D.DSK` | Pascal disks holding the `.TEXT` sources, assembled `.CODE` files, and his built `WIZARDRY.CODE` |
| [SystemStartup/Wiz1StartupPascal.txt](SystemStartup/Wiz1StartupPascal.txt), [Wiz1StartupAssembler.txt](SystemStartup/Wiz1StartupAssembler.txt), `Wiz1E.DSK` | The same for `SYSTEM.STARTUP` (LZDECOMP, CHKSYNCH, SCREENPT) |

The paths above are relative to this directory, `src/appleII/source/ewers_wizardry_i/`. Extract a source file as plain text with the project tools, starting from the GitHub repository root:

```bash
cd src/tools
python3 -m ucsd catalog ../appleII/source/ewers_wizardry_i/WizardryCode/Wiz1C.DSK
python3 -m ucsd extract ../appleII/source/ewers_wizardry_i/WizardryCode/Wiz1C.DSK COMBAT.TEXT --text -o COMBAT.txt
```

## Verification against our boot disk (2026-10-09)

- **Listings match the executables.** `python3 -m ucsd check-listing` decodes every p-code procedure in our boot disk's `WIZARDRY.CODE` and `SYSTEM.STARTUP`: 417 and 47 procedures. All 6,975 + 738 statement offsets in the listings fall on instruction boundaries, and every procedure's size matches. This is strong evidence that the listings describe our binaries exactly.
- **`WIZARDRY.CODE` matches.** All 15 segments are byte-identical to the copy on `Wiz1A.DSK`; only the order of segments within the file differs.
- **`SYSTEM.STARTUP` differs only in copy protection.** It is identical except for 51 bytes in segment WIZBOOT. Ewers's build keeps the Disk II nibble-level protection check, which our deprotected boot image has patched out.
- **Not yet done:** an actual rebuild with Apple Pascal 1.1. That needs the Apple Pascal 1.1 system disks and a four-drive Apple II setup in an emulator. The checks above make the rebuild a confirmation step rather than a prerequisite for the port.

Provenance is in [SOURCES.json](SOURCES.json); after supplying the external files, run `sha256sum -c SHA256SUMS` here to verify.
