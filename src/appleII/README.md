# Apple II reference library

This library is part of the source package under the GitHub repository’s `src/` directory. Run package-level commands from `src/`; run library checksum commands from this library’s own directory.

Wizardry I boot and scenario images are in [images/wizardry_i](images/wizardry_i/README.md), with their own source records, checksums and analysis. Thomas William Ewers's reconstructed source is in [source/ewers_wizardry_i](source/ewers_wizardry_i/README.md), verified against those images. The project's [`ucsd` tools](../tools/ucsd/README.md) read the Pascal disks and disassemble their p-code and native code.

Possible source-platform references, with extra coverage of Apple Pascal because of its relevance to Wizardry I.

## Start here

1. [Wizardry reconstruction README](programming/Wizardry_Reconstruction_README.md): describes a Pascal 1.1 build and credits Thomas William Ewers's reconstruction. The project's v3.2 changes the game; compare against the exact original release you intend to port.
2. [Apple Pascal language reference](programming/Apple_Pascal_Language_Reference.pdf), [OS reference](programming/Apple_Pascal_Operating_System_Reference.pdf), and [1.1 update](programming/Apple_Pascal_Update_1.1.pdf): establish the source language and runtime environment.
3. [Attach-BIOS](programming/Apple_Pascal_1.1_Attach_BIOS.pdf), [Pascal interpreter disassembly](programming/Apple_Pascal_1.1_PCode_Interpreter_Disassembly.pdf), and [p-Source](programming/P_Source_Guide_to_Apple_Pascal_1983.pdf): investigate native interfaces and p-code execution. The disassembly is by Willi Kusche, with introductory correspondence; it is not a disassembly of Wizardry itself.
4. [Pascal filesystem](disk/Pascal_Filesystem.html), [Pascal file structures](disk/Apple_Pascal_File_Formats.html), and [disk-image ordering](disk/Apple_Disk_Image_Formats.html): establish how to locate and extract code and data. Some format notes cite Pascal 1.3; check version-specific structures against the 1.1 references.
5. [Apple II reference](manuals/Apple_II_Reference_Manual_1978.pdf) and [hi-res graphics layout](programming/Apple_II_HiRes_Format.html): understand source-machine memory and display output.

The 1978 Apple II manual predates the IIe. The separate IIe technical manual covers later hardware; do not assume its auxiliary-memory or firmware features exist on an original II/II Plus. Likewise, DOS disk structures from *Beneath Apple DOS* are distinct from Pascal's filesystem. File extensions alone are insufficient to establish disk-sector ordering.

The CiderPress II command-line manual covers host-side disk/file inspection; `cp2` itself is installed by [tools/toolchain](../tools/toolchain/README.md). The cc65 Apple II guide and the shared [assembler/linker/disassembler manuals](../common/README.md) are additional development references; they do not compile Apple Pascal unchanged.

## Local catalog

16 reference files, collected 2026-10-09. PDF page counts refer to the saved files, including covers and front matter.

### Hardware and system manuals

| Local document | Author / publisher | Use for the port | Source |
| --- | --- | --- | --- |
| [Apple II Reference Manual (January 1978)](manuals/Apple_II_Reference_Manual_1978.pdf) (155 PDF pages) | Apple Computer | Original Apple II hardware, graphics, memory map, monitor and schematics; predates IIe. | [Original](https://bitsavers.trailing-edge.com/pdf/apple/apple_II/Apple%5D%5BRefJan78.pdf) |
| [Apple IIe Technical Reference Manual](manuals/Apple_IIe_Technical_Reference_Manual.pdf) (444 PDF pages) | Apple Computer | IIe hardware, auxiliary memory, soft switches and firmware; distinguish IIe features from original II/II Plus. | [Original](https://mirrors.apple2.org.za/Apple%20II%20Documentation%20Project/Computers/Apple%20II/Apple%20IIe/Manuals/Apple%20IIe%20Technical%20Reference%20Manual.pdf) |

### Programming and runtime

| Local document | Author / publisher | Use for the port | Source |
| --- | --- | --- | --- |
| [Apple Pascal Language Reference Manual](programming/Apple_Pascal_Language_Reference.pdf) (120 PDF pages) | Apple Computer | Pascal language, compiler behavior and units for interpreting Wizardry's reconstructed source. | [Original](https://mirrors.apple2.org.za/Apple%20II%20Documentation%20Project/Software/Operating%20Systems/Apple%20Pascal/Manuals/Apple%20Pascal%20Language%20Reference%20Manual.pdf) |
| [Apple Pascal Update 1.1](programming/Apple_Pascal_Update_1.1.pdf) (62 PDF pages) | Apple Computer | Version-specific supplement relevant to the Wizardry reconstruction's Pascal 1.1 environment. | [Original](https://mirrors.apple2.org.za/Apple%20II%20Documentation%20Project/Software/Operating%20Systems/Apple%20Pascal/Manuals/Apple%20Pascal%20Update%201.1.pdf) |
| [Apple II Pascal 1.1 Attach-BIOS](programming/Apple_Pascal_1.1_Attach_BIOS.pdf) (50 PDF pages) | Apple Computer | Pascal BIOS interface reference for investigating platform-dependent I/O. | [Original](https://mirrors.apple2.org.za/Apple%20II%20Documentation%20Project/Software/Operating%20Systems/Apple%20Pascal/Manuals/Apple%20II%20Pascal%201.1%20Attach-BIOS.pdf) |
| [Apple Pascal Operating System Reference Manual](programming/Apple_Pascal_Operating_System_Reference.pdf) (307 PDF pages) | Apple Computer | Pascal system, files, compiler/linker and runtime environment. | [Original](https://mirrors.apple2.org.za/Apple%20II%20Documentation%20Project/Software/Operating%20Systems/Apple%20Pascal/Manuals/Apple%20Pascal%20Operating%20System%20Reference%20Manual.pdf) |
| [Apple II Hi-Res Graphics](programming/Apple_II_HiRes_Format.html) | Andy McFadden / faddenSoft | Hi-res bitmap storage and artifact color for converting source graphics. | [Original](https://ciderpress2.com/formatdoc/HiRes-notes.html) |
| [Wizardry.Code project README](programming/Wizardry_Reconstruction_README.md) | snafaru; credits Thomas William Ewers | Research lead documenting a Pascal 1.1 reconstruction and modified v3.2; not original source provenance. | [Original](https://raw.githubusercontent.com/snafaru/Wizardry.Code/main/README.md) |
| [Apple II Pascal 1.1 p-code interpreter disassembly](programming/Apple_Pascal_1.1_PCode_Interpreter_Disassembly.pdf) (292 PDF pages) | Willi Kusche; introductory correspondence with David Craig | Annotated 6502 runtime disassembly; investigate the boundary between p-code and machine-specific support. | [Original](https://mirrors.apple2.org.za/ftp.apple.asimov.net/documentation/programming/pascal/Apple%202%20Pascal%2011%20PCodeIntDism.pdf) |
| [p-Source: A Guide to the Apple Pascal System (1983)](programming/P_Source_Guide_to_Apple_Pascal_1983.pdf) (462 PDF pages) | Randall Hyde | Pascal runtime internals and p-code for evaluating an interpreter-based port. | [Original](https://mirrors.apple2.org.za/ftp.apple.asimov.net/documentation/programming/pascal/Hyde_P-Source-A%20Guide%20to%20the%20APPLE%20Pascal%20System_1983.pdf) |

### Disks and file formats

| Local document | Author / publisher | Use for the port | Source |
| --- | --- | --- | --- |
| [Beneath Apple DOS](disk/Beneath_Apple_DOS.pdf) (177 PDF pages) | Don Worth and Pieter Lechner | Disk II, DOS internals, sectors and disk structures; distinguish DOS from Pascal disk layout. | [Original](https://mirrors.apple2.org.za/Apple%20II%20Documentation%20Project/Books/Beneath%20Apple%20DOS.pdf) |
| [Apple Pascal Filesystem for the Apple II](disk/Pascal_Filesystem.html) | Andy McFadden / faddenSoft | Directory entries, contiguous allocation and 512-byte blocks. | [Original](https://ciderpress2.com/formatdoc/Pascal-notes.html) |
| [Apple Pascal Textfile and Codefile](disk/Apple_Pascal_File_Formats.html) | Andy McFadden / faddenSoft | Segment dictionaries and Pascal text/code file formats; version distinctions need checking. | [Original](https://ciderpress2.com/formatdoc/ApplePascal-notes.html) |
| [Unadorned Disk Image Files](disk/Apple_Disk_Image_Formats.html) | Andy McFadden / faddenSoft | DOS/ProDOS sector ordering and .dsk/.do/.po/.nib image interpretation. | [Original](https://ciderpress2.com/formatdoc/Unadorned-notes.html) |

### Development and inspection tools

| Local document | Author / publisher | Use for the port | Source |
| --- | --- | --- | --- |
| [CiderPress II command-line manual](tools/CiderPress_II_CLI_Manual.md) | Andy McFadden / faddenSoft | Disk inspection and file extraction/conversion on the host. | [Original](https://raw.githubusercontent.com/fadden/CiderPress2/main/docs/Manual-cp2.md) |
| [cc65 apple2 target reference](tools/apple2.html) | cc65 project | Target memory layout, binary formats, library support and platform-specific conventions. | [Original](https://cc65.github.io/doc/apple2.html) |

## Provenance and offline use

[SOURCES.json](SOURCES.json) records original URLs, retrieval dates, hashes, file sizes and PDF page counts. [SHA256SUMS](SHA256SUMS) verifies the reference files and web assets with `sha256sum -c SHA256SUMS` from this folder.

PDF, text and Markdown documents retain their downloaded bytes. HTML body content is preserved; links to included documents/assets are local, while links to other resources point back to the source website. Original-download and stored-file hashes are both recorded. Some scanned PDFs lack searchable text, and additional web pages linked from the documents require internet access. PDFs are not stored in Git; `python3 tools/fetch_refs.py` from the repository’s `src/` directory downloads and verifies them.

The MOS CPU manual and ca65/ld65/da65 manuals are shared by all three platforms and live in the [common library](../common/README.md). Original copyright/licence notices are retained. See the [project library guide](../RESEARCH.md) for the cross-platform reading order and additional research lead.
