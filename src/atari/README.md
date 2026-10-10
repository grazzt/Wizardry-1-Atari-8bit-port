# Atari 8-bit reference library

This library is part of the source package under the GitHub repository’s `src/` directory. Run package-level commands from `src/`; run library checksum commands from this library’s own directory.

Target-platform references for the Atari 400/800 and XL/XE families. These are Atari 8-bit computer documents, rather than Atari ST or 2600 references.

## Start here

1. [De Re Atari](manuals/De_Re_Atari.pdf): practical graphics, display lists, interrupts, sound and OS use.
2. [Mapping the Atari, revised edition](manuals/Mapping_the_Atari.pdf): memory allocation, OS variables and hardware registers, including XL/XE appendices.
3. [Technical Reference Notes](manuals/Atari_Technical_Reference_Notes_1982.pdf): the original 400/800 OS and hardware manuals, with OS source listings. Read the [XL addendum](manuals/Atari_XL_Operating_System_Addendum.pdf) for later-machine differences.
4. [Altirra Hardware Reference](manuals/Altirra_Hardware_Reference_Manual.pdf): detailed hardware behavior; downloaded edition is 2026-01-02.
5. [Inside Atari DOS](disk/Inside_Atari_DOS.pdf) and [ATR format notes](disk/ATR_Image_Format_and_Tools.md): disk access, filesystem structures and host-side disk images.

For the port, investigate text/bitmap layout, ANTIC display-list memory, keyboard/ATASCII handling, CIO versus SIO disk access, and the memory budget after OS, screen and DOS allocations. Decide the target RAM/model before relying on XL/XE banking or expanded memory. Validate both PAL and NTSC behavior if both are intended targets.

The cc65 target guide and the shared [ca65/ld65 manuals](../common/README.md) provide a possible cross-development route. The MADS English manual is the historical 1.9.5 document, not a claim about the current assembler release. Atari800 documentation provides a portable emulator lead; Altirra's overview documents its Windows debugger and configuration features.

## Local catalog

12 reference files, collected 2026-10-09. PDF page counts refer to the saved files, including covers and front matter.

### Hardware and system manuals

| Local document | Author / publisher | Use for the port | Source |
| --- | --- | --- | --- |
| [Atari Home Computer System Technical Reference Notes (1982)](manuals/Atari_Technical_Reference_Notes_1982.pdf) (537 PDF pages) | Atari | 400/800 OS user's manual, OS source listing and hardware manual; CIO/SIO and hardware programming. | [Original](https://bitsavers.trailing-edge.com/pdf/atari/400_800/CO16555_Atari_Home_Computer_Technical_Reference_Notes_1982.pdf) |
| [Altirra Hardware Reference Manual (2026-01-02 edition)](manuals/Altirra_Hardware_Reference_Manual.pdf) (527 PDF pages) | Avery Lee | Detailed Atari hardware behavior, ANTIC, GTIA, POKEY, memory and timing; includes later machines. | [Original](https://www.virtualdub.org/downloads/Altirra%20Hardware%20Reference%20Manual.pdf) |
| [De Re Atari](manuals/De_Re_Atari.pdf) (244 PDF pages) | Atari / Atari Program Exchange | Practical display lists, scrolling, interrupts, player/missile graphics, sound and OS techniques. | [Original](https://seriouscomputerist.atariverse.com/media/pdf/book/De%20Re%20Atari.pdf) |
| [Mapping the Atari, Revised Edition (1985)](manuals/Mapping_the_Atari.pdf) (305 PDF pages) | Ian Chadwick | Address-by-address OS and hardware memory map, including XL/XE appendices. | [Original](https://seriouscomputerist.atariverse.com/media/pdf/book/Mapping%20the%20Atari.pdf) |
| [Atari XL Addendum — Operating System Manual](manuals/Atari_XL_Operating_System_Addendum.pdf) (447 PDF pages) | Atari | XL memory/OS changes; supplement to the 400/800 reference. | [Original](https://seriouscomputerist.atariverse.com/media/pdf/book/Atari%20XL%20Addendum%20-%20Operating%20System%20Manual.pdf) |

### Disks and file formats

| Local document | Author / publisher | Use for the port | Source |
| --- | --- | --- | --- |
| [Atari Disk Operating System Reference Manual](disk/Atari_DOS_Reference_Manual.pdf) (77 PDF pages) | Atari | Disk commands and file operations; consult the PDF title/version before applying to a particular DOS. | [Original](https://www.atarimania.com/documents/Disk_Operating_System_Reference_Manual.pdf) |
| [Inside Atari DOS](disk/Inside_Atari_DOS.pdf) (130 PDF pages) | Bill Wilkinson, Kathleen O’Brien and Paul Laughton | DOS internals and disk file management for a loader or save-game implementation. | [Original](https://seriouscomputerist.atariverse.com/media/pdf/book/Inside%20Atari%20DOS.pdf) |
| [Atari disk tools and ATR format notes](disk/ATR_Image_Format_and_Tools.md) | Joseph H. Allen | ATR headers, sector sizing and disk-image conversion notes. | [Original](https://raw.githubusercontent.com/jhallen/atari-tools/master/readme.md) |

### Development and inspection tools

| Local document | Author / publisher | Use for the port | Source |
| --- | --- | --- | --- |
| [MADS English manual (1.9.5)](tools/MADS_English_Manual.html) | Tebe / Madteam; translation by Phaeron | Atari-focused assembler syntax, macros, banking and executable formats; historical manual version. | [Original](https://mads.atari8.info/mads_eng.html) |
| [cc65 atari target reference](tools/atari.html) | cc65 project | Target memory layout, binary formats, library support and platform-specific conventions. | [Original](https://cc65.github.io/doc/atari.html) |
| [Atari800 emulator documentation](tools/Atari800_README.txt) | Atari800 development team | Portable emulator configuration and operation; useful for a Linux development host. | [Original](https://raw.githubusercontent.com/atari800/atari800/master/DOC/README) |
| [Altirra emulator overview and documentation links](tools/Altirra_Overview.html) | Avery Lee | Debugger and machine-configuration overview; the hardware reference is saved separately. | [Original](https://www.virtualdub.org/altirra.html) |

## Provenance and offline use

[SOURCES.json](SOURCES.json) records original URLs, retrieval dates, hashes, file sizes and PDF page counts. [SHA256SUMS](SHA256SUMS) verifies the reference files and web assets with `sha256sum -c SHA256SUMS` from this folder.

PDF, text and Markdown documents retain their downloaded bytes. HTML body content is preserved; links to included documents/assets are local, while links to other resources point back to the source website. Original-download and stored-file hashes are both recorded. Some scanned PDFs lack searchable text, and additional web pages linked from the documents require internet access. PDFs are not stored in Git; `python3 tools/fetch_refs.py` from the repository’s `src/` directory downloads and verifies them.

The MOS CPU manual and ca65/ld65/da65 manuals are shared by all three platforms and live in the [common library](../common/README.md). Original copyright/licence notices are retained. See the [project library guide](../RESEARCH.md) for the cross-platform reading order and additional research lead.
