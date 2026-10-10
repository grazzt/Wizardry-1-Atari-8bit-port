#!/usr/bin/env bash
set -euo pipefail
RETRO_TOOLS="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
RETRO_PROJECT="$(cd -- "$RETRO_TOOLS/../.." && pwd)"
export XDG_CACHE_HOME="$RETRO_TOOLS/state/cache"
export XDG_CONFIG_HOME="$RETRO_TOOLS/state/config"
export XDG_DATA_HOME="$RETRO_TOOLS/state/data"
mkdir -p "$XDG_CACHE_HOME" "$XDG_CONFIG_HOME" "$XDG_DATA_HOME"

prepare_disks() {
    local platform="$1" suffix="$2" image
    mkdir -p "$RETRO_TOOLS/state/$platform-disks"
    for image in "$RETRO_PROJECT/$platform/images/wizardry_i/"*".$suffix"; do
        if [[ ! -f "$RETRO_TOOLS/state/$platform-disks/$(basename -- "$image")" ]]; then
            cp -- "$image" "$RETRO_TOOLS/state/$platform-disks/"
        fi
    done
}
