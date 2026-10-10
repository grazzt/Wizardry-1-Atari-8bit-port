# `ucsd` — Apple Pascal disk, code-file and p-code tools

Pure-Python (3.10+, no dependencies) tools for reading Apple Pascal 1.1 (UCSD II.1) volumes and code files. They are checked against Ewers's compiler listings: every statement offset in both Wizardry listings decodes to an instruction boundary.

From the GitHub repository root, enter `src/tools` to run these examples. Other package paths in this guide are relative to `src/`.

```bash
cd src/tools
python3 -m ucsd catalog  IMAGE                       # volume directory, with Pascal file dates
python3 -m ucsd extract  IMAGE NAME [-o OUT] [--text] # raw bytes, or a .TEXT file as plain text
python3 -m ucsd segments IMAGE [CODEFILE]            # segment dictionary and sizes
python3 -m ucsd disasm   IMAGE [CODEFILE] [--segment NAME|NUM] [--proc N]
python3 -m ucsd natives  IMAGE [CODEFILE]            # everything machine-specific
python3 -m ucsd check-listing IMAGE LISTING [CODEFILE]
python3 -m unittest discover -s ucsd/tests -t .      # regression tests
```

`CODEFILE` defaults to `WIZARDRY.CODE`. Images may be DOS-order (`.dsk`) or ProDOS-order (`.po`); the order is detected from the volume directory.

| Module | Contents |
| --- | --- |
| `disk.py` | 140K image → 512-byte blocks, Pascal directory, file reads, `.TEXT` decoding |
| `codefile.py` | Segment dictionary; procedure dictionaries and attribute tables |
| `pcode.py` | II.1 opcode table and decoder; CSP standard-procedure names; confirmed `PASCALSY` entry points |
| `m6502.py` | Native-procedure layout (code plus four relocation lists) and a small 6502 disassembler |

Disassembly output gives offsets relative to the procedure entry, matching the IC column of Ewers's listing. A `>` marks the procedure's EXITIC. Jump targets are absolute offsets within the segment.

## What the tools show about Wizardry I

These measurements are from the project's boot disk (`appleII/images/wizardry_i/wizardry_i_boot.dsk`).

**Code size.** `WIZARDRY.CODE` contains 68,802 bytes of code in 15 segments, with 417 p-code procedures and 7 native ones.

- The resident segment WIZARDRY is 3,410 bytes.
- The largest overlay is UTILITIE at 7,766 bytes; the next are CUTIL (7,014) and SHOPS (7,012).
- Resident plus largest overlay is 11,176 bytes of code.
- `SYSTEM.STARTUP` (title, options and chaining) is 10,234 bytes and runs before the game, not alongside it.

**Machine-specific code.** Only three things are machine-specific:

1. **The interpreter and BIOS, `RTSTRP.APPLE` (12,288 bytes).** This is the game's own runtime, not Apple's standard `SYSTEM.APPLE`. It is a stripped p-machine loaded at `$9200`; see the [runtime notes](../../appleII/images/wizardry_i/README.md#the-runtime-rtstrpapple).
2. **Seven native routines in segment 1** (1,094 bytes in total):

   | Proc | Routine | Bytes | Machine dependencies |
   | --- | --- | ---: | --- |
   | 26 | CLRPICT | 210 | Hi-res memory through a relocated row table; scratch in text-page "screen holes" `$0679`/`$06F9`/`$0779`/`$07F9` |
   | 27 | DRAWLINE | 426 | Same screen holes; inline data tables (the `.BYTE`/odd addresses in its disassembly) |
   | 28 | RANDOM | 58 | **RNG state lives in screen holes `$047A`/`$04FA`/`$057A`/`$05FB`** |
   | 29 | KEYAVAIL | 46 | Language-card switching (`$C083`/`$C08B`); Pascal BIOS keyboard poll `JSR $BF0A`; buffer pointers `$BF18`/`$BF19` |
   | 30 | CLRRECT | 100 | Hi-res memory only, through the relocated row table |
   | 31 | MVCURSOR | 138 | Keyboard `$C000`; display soft switches `$C050`–`$C057`; BIOS keyboard; screen holes |
   | 32 | PRGRCHR | 116 | Hi-res page addresses `$2080`/`$20A8`; screen holes |

   All seven use zero page `$00`–`$0F` (up to `$2A`) as scratch. On the Atari, `$00`–`$7F` belongs to the OS.
3. **Pascal I/O, which bottoms out in BIOS calls.** `SYSTEM.PASCAL` contains no native code: the whole OS is p-code.

**What the game calls.** The game uses these standard procedures: EXIT, MOVELEFT, FILLCHAR, UNITREAD/UNITWRITE/UNITCLEAR, IORESULT, RELEASE and HALT. From the OS (`CXP 0,n`) it uses only WRITE (char, string, integer), WRITELN, READ(char), READLN, EOLN, GOTOXY, CONCAT and COPY. It calls no `SYSTEM.LIBRARY` units. `SYSTEM.STARTUP` additionally uses CHAINSTUFF to chain into the game.

**Floating point.** No REAL arithmetic opcodes appear anywhere in `WIZARDRY.CODE`.

## Not yet covered

- The comparison type byte for `EQU`/`NEQ`/… follows the II.0 documentation. Wizardry only uses the string and multi-word types, so the others are untested.
- p-code that uses absolute addresses (`LDCI` constants as pointers) has not been searched for systematically. Running the game in [`pvm`](../pvm/README.md) has shown `$2000` (copy-protection code load), `$4000` (heap start) and `$0479` (copy-protection marker).
- The disassembler does not yet separate inline data from code in native routines; use `da65` with an info file for those.
