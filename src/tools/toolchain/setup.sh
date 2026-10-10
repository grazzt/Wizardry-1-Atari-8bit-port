#!/usr/bin/env bash
# Install the Git-ignored cross-development tools (cc65, CiderPress II) under
# this directory from the pins in SOURCES.json. Safe to re-run.
#
#   tools/toolchain/setup.sh
#   source tools/toolchain/env.sh     # puts cl65/ca65/ld65/da65/cp2 on PATH
set -euo pipefail
cd -- "$(dirname -- "$0")"
ROOT="$PWD"
for cmd in curl git python3 gcc make unzip sha256sum; do
    command -v "$cmd" >/dev/null || { echo "setup: missing required command: $cmd" >&2; exit 1; }
done
mkdir -p downloads src local logs
pin() { python3 -c "import json; d = json.load(open('SOURCES.json')); print($1)"; }

# --- cc65 ---------------------------------------------------------------------
cc65_commit="$(pin "d['cc65']['commit']")"
if [[ ! -d src/cc65/.git ]]; then
    echo "setup: cloning cc65"
    git clone -q "$(pin "d['cc65']['url']")" src/cc65
fi
if [[ "$(git -C src/cc65 rev-parse HEAD)" != "$cc65_commit" || ! -x local/bin/ca65 ]]; then
    git -C src/cc65 checkout -q --detach "$cc65_commit"
    echo "setup: building cc65 (logs/cc65-build.log; a few minutes)"
    make -C src/cc65 -j"$(nproc)" PREFIX="$ROOT/local" > logs/cc65-build.log 2>&1
    make -C src/cc65 install PREFIX="$ROOT/local" > logs/cc65-install.log 2>&1
fi

# --- CiderPress II --------------------------------------------------------------
cp2_zip=downloads/cp2.zip
cp2_sha="$(pin "d['ciderpress2']['sha256']")"
if ! { [[ -f $cp2_zip ]] && echo "$cp2_sha  $cp2_zip" | sha256sum -c --quiet --status; }; then
    echo "setup: downloading CiderPress II"
    curl -fsSL -o "$cp2_zip.tmp" "$(pin "d['ciderpress2']['url']")"
    echo "$cp2_sha  $cp2_zip.tmp" | sha256sum -c --quiet || { rm -f "$cp2_zip.tmp"; exit 1; }
    mv -- "$cp2_zip.tmp" "$cp2_zip"
    rm -rf local/cp2
fi
if [[ ! -x local/cp2/cp2 ]]; then
    mkdir -p local/cp2
    unzip -q -o "$cp2_zip" -d local/cp2
    # The archive may contain a versioned top-level folder; flatten it.
    if [[ ! -e local/cp2/cp2 ]]; then
        inner="$(dirname -- "$(find local/cp2 -name cp2 -type f | head -1)")"
        mv -- "$inner"/* local/cp2/ && rmdir -- "$inner"
    fi
    chmod +x local/cp2/cp2
fi

echo "setup: $(local/bin/ca65 --version 2>&1 | head -1)"
echo "setup: $(local/cp2/cp2 version 2>&1 | head -1)"
