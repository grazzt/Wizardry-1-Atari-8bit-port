# Source this file to use the project toolchain: source tools/toolchain/env.sh
_toolchain="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export PATH="$_toolchain/local/bin:$_toolchain/local/cp2:$PATH"
export CC65_HOME="$_toolchain/local/share/cc65"
unset _toolchain
