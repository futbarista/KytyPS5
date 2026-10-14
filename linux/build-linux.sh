#!/bin/bash
# The Linux (SteamOS) build of this tree and its portable package, the counterpart of the Windows release workflow
# (.github/workflows/build.yml): clang 19, x86-64-v3, ThinLTO, in an Ubuntu 24.04 distrobox (SteamOS's root is
# read-only). Usage: linux/build-linux.sh [package dir] (default: ../KytyPS5 next to the source tree).
set -euo pipefail
SRC="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
OUT="${1:-$(dirname "$SRC")/KytyPS5}"
BOX="${KYTY_DISTROBOX:-kyty-build}"
BUILD="$SRC/_Build/linux"
in_box() { if [ -f /run/.containerenv ] || [ -f /.dockerenv ]; then bash -c "$1"; else distrobox enter "$BOX" -- bash -c "$1"; fi; }
if ! distrobox list 2>/dev/null | grep -q " $BOX " && [ ! -f /run/.containerenv ]; then
	distrobox create -Y -n "$BOX" -i docker.io/library/ubuntu:24.04
fi
in_box "command -v clang++-19 >/dev/null && command -v glslangValidator >/dev/null || sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
	clang-19 lld-19 llvm-19 ninja-build cmake git glslang-tools python3 pkg-config libgl1-mesa-dev libx11-dev libxcursor-dev \
	libxext-dev libxfixes-dev libxi-dev libxrandr-dev libxss-dev libxkbcommon-dev libasound2-dev libpulse-dev libudev-dev \
	libdbus-1-dev libwayland-dev wayland-protocols libdecor-0-dev zlib1g-dev libbz2-dev liblzma-dev"
if [ ! -f "$BUILD/build.ninja" ]; then
	in_box "cmake -S '$SRC' -B '$BUILD' -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=clang-19 -DCMAKE_CXX_COMPILER=clang++-19 \
		-DCMAKE_AR=/usr/bin/llvm-ar-19 -DCMAKE_RANLIB=/usr/bin/llvm-ranlib-19 -DKYTY_BUILD_LAUNCHER=OFF -DBUILD_TESTING=OFF \
		'-DCMAKE_C_FLAGS=-march=x86-64-v3 -flto=thin' '-DCMAKE_CXX_FLAGS=-march=x86-64-v3 -flto=thin' \
		'-DCMAKE_EXE_LINKER_FLAGS=-fuse-ld=lld -flto=thin -Wl,--thinlto-jobs=all' '-DCMAKE_SHARED_LINKER_FLAGS=-fuse-ld=lld -flto=thin'"
fi
in_box "cmake --build '$BUILD' --target kyty_emulator kyty_shader_precompile zarchive_tool --parallel \$(nproc)"

# The package: as the Windows release's, with the Linux programs and scripts.
mkdir -p "$OUT/tools/local/static-precompile"
install -m755 "$BUILD/kyty_emulator" "$BUILD/kyty_shader_precompile" "$OUT/"
# Without the debug info (-g: 150 MB each), with the symbols (the crash reports' function names).
in_box "llvm-strip-19 --strip-debug '$OUT/kyty_emulator' '$OUT/kyty_shader_precompile'"
ZAR="$(find "$BUILD/3rdparty" -maxdepth 2 -type f -name zarchive -perm -u+x | head -1)"
[ -n "$ZAR" ] && install -m755 "$ZAR" "$OUT/zarchive"
install -m755 "$SRC"/linux/{launcher.sh,run.sh,precompile.sh,launcher-linux.py,run-linux.py,precompile-linux.py} "$OUT/"
install -m644 "$SRC/linux/kyty_common.py" "$SRC/linux/README-LINUX.md" "$SRC/LICENSE" "$OUT/"
install -m644 "$SRC/docs/PORTABLE-README.md" "$OUT/README.md"
cp -r "$SRC/LICENSES" "$OUT/"
[ -f "$OUT/launch.json" ] || install -m644 "$SRC/run-windows.json" "$OUT/launch.json"
install -m644 "$SRC"/tools/local/static-precompile/pass-states.json "$SRC"/tools/local/static-precompile/hints-*.hints \
	"$OUT/tools/local/static-precompile/"
# Double-click in Dolphin (and "Add to Steam"): the launcher, the game, the precompile.
desktop() { # file name exec terminal
	cat > "$OUT/$1" <<EOD
[Desktop Entry]
Type=Application
Name=$2
Exec=$3
Path=$OUT
Terminal=$4
Icon=applications-games
Categories=Game;Emulator;
EOD
	chmod +x "$OUT/$1"
}
desktop 'KytyPS5 Launcher.desktop' 'KytyPS5 Launcher' "\"$OUT/launcher.sh\"" false
desktop 'KytyPS5 Play.desktop' 'KytyPS5 (Demon'"'"'s Souls)' "konsole -e \"$OUT/run.sh\"" false
desktop 'KytyPS5 Precompile.desktop' 'KytyPS5 Precompile shaders' "konsole -e \"$OUT/precompile.sh\"" false
echo "package: $OUT"
