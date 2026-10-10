# Shared 6502 reference library

This library is part of the source package under the GitHub repository’s `src/` directory. Run package-level commands from `src/`; run library checksum commands from this library’s own directory.

All three platforms (Apple II, Atari 8-bit, C64) use the same 6502 instruction family and the same cc65 assembler, linker and disassembler documentation. Those documents are stored once here. Each platform folder keeps its own cc65 target guide (`apple2.html`, `atari.html`, `c64.html`), which links to the shared ca65 manual here.

## Local catalog

4 reference files, collected 2026-10-09.

| Local document | Author / publisher | Use for the port | Source |
| --- | --- | --- | --- |
| [MCS6500 Microcomputer Family Programming Manual (January 1976)](programming/MOS_6500_Programming_Manual_1976.pdf) (262 PDF pages) | MOS Technology | Shared NMOS 6502-family instruction set, addressing modes, flags, arithmetic and interrupts. | [Original](https://bitsavers.trailing-edge.com/components/mosTechnology/6500-50A_MCS6500pgmManJan76.pdf) |
| [ca65 macro assembler manual](tools/ca65.html) | cc65 project | 6502 assembly syntax, directives, macros and object generation. | [Original](https://cc65.github.io/doc/ca65.html) |
| [ld65 linker manual](tools/ld65.html) | cc65 project | Linker configuration, memory regions and segment placement. | [Original](https://cc65.github.io/doc/ld65.html) |
| [da65 disassembler manual](tools/da65.html) | cc65 project | 6502 disassembly and control files for classifying code and data. | [Original](https://cc65.github.io/doc/da65.html) |

## Provenance

[SOURCES.json](SOURCES.json) and [SHA256SUMS](SHA256SUMS) follow the same format as the platform folders. PDFs are not stored in Git; run `python3 tools/fetch_refs.py` from the repository’s `src/` directory to download and verify them. See the [project library guide](../RESEARCH.md).
