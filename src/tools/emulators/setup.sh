#!/usr/bin/env bash
# Rebuild the Git-ignored emulator installation (downloads/, src/, local/)
# from the pinned versions, URLs and hashes in SOURCES.json. Safe to re-run:
# completed steps are skipped.
#
#   tools/emulators/setup.sh                    # emulators and MCP servers
#   tools/emulators/setup.sh --with-reference-sources
#                                               # also clone web-a2e and applem-core
#
# Requires curl, git, python3, node, gcc/make, dpkg-deb and SDL2 development
# headers. VICE additionally needs this machine's GTK3 runtime libraries.
set -euo pipefail
cd -- "$(dirname -- "$0")"
ROOT="$PWD"
with_sources=0
[[ "${1:-}" == --with-reference-sources ]] && with_sources=1

for cmd in curl git python3 node gcc make dpkg-deb sdl2-config sha256sum; do
    command -v "$cmd" >/dev/null || { echo "setup: missing required command: $cmd" >&2; exit 1; }
done
mkdir -p downloads src local logs

pin() {  # pin <python expression over SOURCES.json as d>
    python3 -c "import json; d = json.load(open('SOURCES.json')); print($1)"
}
sha_of() { pin "next(f['sha256'] for f in d['files'] if f['path'] == '$1')"; }

fetch() {  # fetch <url> <dest> <sha256>
    local url="$1" dest="$2" sha="$3"
    if [[ -f "$dest" ]] && echo "$sha  $dest" | sha256sum -c --quiet --status; then
        return
    fi
    echo "setup: downloading $url"
    mkdir -p "$(dirname -- "$dest")"
    curl -fsSL --connect-timeout 15 -o "$dest.tmp" "$url"
    if ! echo "$sha  $dest.tmp" | sha256sum -c --quiet --status; then
        echo "setup: hash mismatch for $url" >&2
        rm -f "$dest.tmp"
        exit 1
    fi
    mv -- "$dest.tmp" "$dest"
}

clone_at() {  # clone_at <name in SOURCES.json repositories>
    local name="$1" url commit
    url="$(pin "d['repositories']['$name']['url']")"
    commit="$(pin "d['repositories']['$name']['commit']")"
    if [[ ! -d "src/$name/.git" ]]; then
        echo "setup: cloning $url"
        git clone -q "$url" "src/$name"
    fi
    git -C "src/$name" checkout -q --detach "$commit"
}

# --- C64: VICE from the Ubuntu package, plus ROMs Debian does not ship -------
fetch "$(pin "d['sources']['vice_package']")" downloads/vice.deb "$(sha_of downloads/vice.deb)"
if [[ ! -x local/usr/bin/x64sc ]]; then
    echo "setup: extracting VICE"
    dpkg-deb -x downloads/vice.deb local
fi
rom_base="$(pin "d['sources']['vice_rom_base']")"
for rom in C64/kernal-901227-03.bin C64/basic-901226-01.bin C64/chargen-901225-01.bin \
           DRIVES/dos1541-325302-01+901229-05.bin; do
    fetch "$rom_base$rom" "local/usr/share/vice/$rom" "$(sha_of "local/usr/share/vice/$rom")"
done

# --- Atari: Atari800 built from source with SDL2 -----------------------------
fetch "$(pin "d['sources']['atari800_source']")" downloads/atari800-src.tgz "$(sha_of downloads/atari800-src.tgz)"
if [[ ! -x local/bin/atari800 ]]; then
    echo "setup: building Atari800 (logs/atari800-*.log)"
    tar -xzf downloads/atari800-src.tgz -C src
    (
        cd src/atari800-7.2.1
        ./configure --prefix="$ROOT/local" --disable-riodevice > "$ROOT/logs/atari800-configure.log" 2>&1
        make -j"$(nproc)" > "$ROOT/logs/atari800-build.log" 2>&1
        make install > "$ROOT/logs/atari800-install.log" 2>&1
    )
fi

# --- libatari800: Atari800 as a library, for the scripted port tests --------
if [[ ! -f local/lib/libatari800.so ]]; then
    echo "setup: building libatari800 (logs/libatari800-*.log)"
    rm -rf src/atari800-lib
    mkdir -p src/atari800-lib local/lib
    tar -xzf downloads/atari800-src.tgz -C src/atari800-lib --strip-components=1
    (
        cd src/atari800-lib
        CFLAGS="-O2 -fPIC" ./configure --target=libatari800 --disable-riodevice \
            > "$ROOT/logs/libatari800-configure.log" 2>&1
        sed -i 's/ -Werror//g' src/Makefile     # a harmless ULONG redefinition warning
        make -j"$(nproc)" > "$ROOT/logs/libatari800-build.log" 2>&1
    )
    # The archive holds duplicate members; link the object files directly.
    mapfile -t objs < <(find src/atari800-lib/src -name '*.o' ! -name 'test-*' ! -name 'guess_settings-*')
    gcc -shared -o local/lib/libatari800.so "${objs[@]}" -lz -lpng -lm -lpthread
fi

# --- Apple II: deployed web-a2e snapshot --------------------------------------
apple_base="$(pin "d['sources']['apple_web_snapshot']")"
pin "'\n'.join(f['path'] + ' ' + f['sha256'] for f in d['files'] if f['path'].startswith('local/web-a2e/'))" |
while read -r path sha; do
    fetch "$apple_base${path#local/web-a2e/}" "$path" "$sha"
done

# --- MCP servers: pinned checkouts, locked npm archives, no lifecycle scripts --
clone_at vice-mcp
clone_at appleii-agent-git
patch=config/appleii-loopback.patch
if ! git -C src/appleii-agent-git apply --reverse --check "$ROOT/$patch" 2>/dev/null; then
    git -C src/appleii-agent-git apply "$ROOT/$patch"
fi
if [[ ! -x src/vice-mcp/node_modules/.bin/tsup || ! -d src/appleii-agent-git/node_modules ]]; then
    python3 install_node_locked.py prepare
    echo "setup: downloading npm archives"
    curl -K downloads/npm.curl
    python3 install_node_locked.py install
fi
if [[ ! -f src/vice-mcp/dist/index.js ]]; then
    echo "setup: building vice-mcp"
    (cd src/vice-mcp && node_modules/.bin/tsup src/index.ts --format esm --dts --clean) \
        > logs/vice-mcp-build.log 2>&1
fi

if (( with_sources )); then
    clone_at web-a2e
    clone_at applem-core
fi

# Downloads must match exactly. Built files (atari800, vice-mcp's dist) can
# differ with compiler version or install path; report those without failing.
if sha256sum -c --quiet SHA256SUMS 2>/dev/null; then
    echo "setup: complete; all SHA256SUMS entries match"
else
    echo "setup: complete; the entries listed above differ from SHA256SUMS (expected only for built files)"
fi
