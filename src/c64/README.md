# Commodore 64 reference library

This library is part of the source package under the GitHub repository’s `src/` directory. Run package-level commands from `src/`; run library checksum commands from this library’s own directory.

Wizardry I side A and side B image provenance is recorded in [images/wizardry_i](images/wizardry_i/README.md), with their own source records and checksums.

Possible source-platform references for inspecting the C64 implementation and identifying hardware-dependent routines.

## Start here

1. [Commodore 64 Programmer's Reference Guide](manuals/Commodore_64_Programmers_Reference_Guide.pdf): official coverage of memory, VIC-II, SID, KERNAL calls, I/O and assembly. The searchable text transcription was used during research but is not distributed here.
2. *Mapping the Commodore 64*: address-by-address reference for identifying ROM calls, system variables and hardware registers.
3. [VIC-II reference](programming/VIC_II_Reference.txt): Christian Bauer's detailed research on display modes and video timing.
4. [1541 User's Guide](disk/Commodore_1541_Users_Guide.pdf) and [D64 format specification](disk/D64_Format.txt): drive commands, file access and disk-image structure.
5. [VICE monitor documentation](tools/VICE_Monitor.html): breakpoints, disassembly, memory inspection and execution tracing.

When comparing implementations, investigate the 6510 processor-port memory configuration, RAM beneath ROM/I/O, KERNAL and serial-drive interfaces, character encoding, keyboard scanning and bitmap addressing. Sharing the 6502 instruction family does not make these machine interfaces interchangeable with Atari's.

The 1541 is a separate processor-equipped disk drive; determine whether the particular game release uses standard DOS calls or custom drive code. A D64 image describes sectors and may not preserve every feature of an original disk. The shared [MOS programming manual](../common/programming/MOS_6500_Programming_Manual_1976.pdf) covers the 6502 instruction family; use the C64 references for 6510-specific integration.

The cc65 C64 guide and the shared [ca65/ld65/da65 manuals](../common/README.md) provide assembler, linker and disassembly references without committing the port to that toolchain.

## Research catalog

8 catalogued references, collected 2026-10-09. PDFs and the two book transcriptions are external references and are not included. PDF page counts refer to the saved files, including covers and front matter.

### Hardware and system manuals

| Local document | Author / publisher | Use for the port | Source |
| --- | --- | --- | --- |
| [Commodore 64 Programmer’s Reference Guide](manuals/Commodore_64_Programmers_Reference_Guide.pdf) (508 PDF pages) | Commodore | Memory map, VIC-II graphics, SID sound, KERNAL calls, 6510 assembly and I/O. | [Original](https://www.zimmers.net/anonftp/pub/cbm/c64/manuals/C64_Programmers_Reference_Guide.pdf) |
| Commodore 64 Programmer’s Reference Guide (searchable transcription) | Commodore; Project 64 transcription | Searchable companion to the original manual. | Research reference only; book text not included |
| *Mapping the Commodore 64* | Sheldon Leemon; Project 64 transcription | Address-by-address memory and ROM reference for tracing the source platform. | Research reference only; book text not included |

### Programming and runtime

| Local document | Author / publisher | Use for the port | Source |
| --- | --- | --- | --- |
| [The MOS 6567/6569 video controller (VIC-II) and its application in the Commodore 64](programming/VIC_II_Reference.txt) | Christian Bauer | Detailed VIC-II register, display and timing research. | [Original](https://www.cebix.net/VIC-Article.txt) |

### Disks and file formats

| Local document | Author / publisher | Use for the port | Source |
| --- | --- | --- | --- |
| [Commodore 1541 User’s Guide](disk/Commodore_1541_Users_Guide.pdf) (78 PDF pages) | Commodore | Drive command channel, sequential/relative files, direct-access commands and error handling. | [Original](https://www.zimmers.net/anonftp/pub/cbm/manuals/drives/1541_Users_Guide.pdf) |
| [D64 file format specification](disk/D64_Format.txt) | Peter Schepers | Disk-image geometry, BAM, directory entries, file chains and error bytes. | [Original](https://ist.uwaterloo.ca/~schepers/formats/D64.TXT) |

### Development and inspection tools

| Local document | Author / publisher | Use for the port | Source |
| --- | --- | --- | --- |
| [VICE monitor documentation](tools/VICE_Monitor.html) | VICE team | VICE monitor commands for disassembly, breakpoints, watchpoints and memory inspection (chapter 12). | [Original](https://vice-emu.sourceforge.io/vice_12.html) |
| [cc65 c64 target reference](tools/c64.html) | cc65 project | Target memory layout, binary formats, library support and platform-specific conventions. | [Original](https://cc65.github.io/doc/c64.html) |

## Provenance and offline use

[SOURCES.json](SOURCES.json) records original URLs, retrieval dates, hashes, file sizes and PDF page counts. [SHA256SUMS](SHA256SUMS) verifies the reference files and web assets with `sha256sum -c SHA256SUMS` from this folder.

PDF, text and Markdown documents retain their downloaded bytes. HTML body content is preserved; links to included documents/assets are local, while links to other resources point back to the source website. Original-download and stored-file hashes are both recorded. Some scanned PDFs lack searchable text, and additional web pages linked from the documents require internet access. Book transcriptions remain documented as research sources but are neither included nor fetched by the helper. PDFs are not stored in Git; `python3 tools/fetch_refs.py` from the repository’s `src/` directory downloads and verifies them.

The MOS CPU manual and ca65/ld65/da65 manuals are shared by all three platforms and live in the [common library](../common/README.md). Original copyright/licence notices are retained. See the [project library guide](../RESEARCH.md) for the cross-platform reading order and additional research lead.
