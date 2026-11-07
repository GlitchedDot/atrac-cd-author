#!/bin/bash
# Build the fully native DiscWright.app (Step 3: SwiftUI face +
# byte-proven Swift core + the vendored atracdenc encoder).
# Run in Terminal (macOS):
#     cd <this folder>
#     ./build-app.sh
#     open DiscWright.app
# The bundle lands next to this script. No Xcode project, no
# SwiftPM — plain swiftc, like build-selftest.sh.
set -e
cd "$(dirname "$0")"

if ! xcrun --find swiftc >/dev/null 2>&1; then
  echo "The Swift compiler was not found."
  echo "Install Apple's free Command Line Tools first, in Terminal:"
  echo "    xcode-select --install"
  echo "When that finishes, run ./build-app.sh again."
  exit 1
fi

# ---- Step 3 dependencies: cmake + libsndfile ----------------
# atracdenc (the vendored encoder) builds with CMake and reads
# WAVs through libsndfile on macOS. Both come from Homebrew.
# Nothing is installed automatically — if either is missing we
# stop here, before compiling anything, with the exact fix.
SNDFILE_PREFIX=""
if command -v brew >/dev/null 2>&1; then
  SNDFILE_PREFIX="$(brew --prefix libsndfile 2>/dev/null || true)"
fi
HAVE_SNDFILE=0
if [ -n "$SNDFILE_PREFIX" ] && [ -e "$SNDFILE_PREFIX/lib/libsndfile.dylib" ]; then
  HAVE_SNDFILE=1
elif ls /opt/homebrew/lib/libsndfile.* /usr/local/lib/libsndfile.* >/dev/null 2>&1; then
  HAVE_SNDFILE=1
elif command -v pkg-config >/dev/null 2>&1 && pkg-config --exists sndfile; then
  HAVE_SNDFILE=1
fi
if ! command -v cmake >/dev/null 2>&1 || [ "$HAVE_SNDFILE" -eq 0 ]; then
  echo "DiscWright needs two free build tools for its encoder (atracdenc):"
  command -v cmake >/dev/null 2>&1 || echo "  - cmake: MISSING"
  [ "$HAVE_SNDFILE" -eq 1 ] || echo "  - libsndfile: MISSING"
  echo ""
  echo "Install them with Homebrew, in Terminal:"
  echo "    brew install cmake libsndfile"
  echo "Then run ./build-app.sh again. (Nothing else to do — the"
  echo "encoder builds once and is reused until its sources change.)"
  exit 1
fi

# ---- atracdenc: build once, reuse until sources change ------
ENC_SRC="encoder/atracdenc-src"
ENC_BUILD="encoder/build"
ENC_BIN="$ENC_BUILD/src/atracdenc"
ENC_STAMP="$ENC_BUILD/.source-stamp"
NEW_STAMP="$(find "$ENC_SRC" -type f -print0 | sort -z | xargs -0 shasum -a 256 | shasum -a 256 | cut -d' ' -f1)"
OLD_STAMP=""
[ -f "$ENC_STAMP" ] && OLD_STAMP="$(cat "$ENC_STAMP")"
if [ -x "$ENC_BIN" ] && [ "$NEW_STAMP" = "$OLD_STAMP" ]; then
  echo "atracdenc: up to date (skipping rebuild)."
else
  echo "Building atracdenc (one-time; native $(uname -m))..."
  CMAKE_PREFIX_ARGS=()
  if command -v brew >/dev/null 2>&1; then
    BREW_PREFIX="$(brew --prefix 2>/dev/null || true)"
    [ -n "$BREW_PREFIX" ] && CMAKE_PREFIX_ARGS=(-DCMAKE_PREFIX_PATH="$BREW_PREFIX")
  fi
  # GTest is disabled explicitly: the upstream test/ tree is not
  # vendored, and the top-level CMake only adds it when GTest is
  # found. Architecture: the HOST's own arch (uname -m) — the
  # encoder links this machine's libsndfile, which is
  # single-arch (Intel Homebrew = x86_64); upstream's forced
  # universal binary failed to link its arm64 slice
  # (GlitchedDot's build, 2026-11-05). The vendored CMakeLists
  # is patched to respect this override.
  cmake -S "$ENC_SRC" -B "$ENC_BUILD" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_OSX_ARCHITECTURES="$(uname -m)" \
    -DCMAKE_DISABLE_FIND_PACKAGE_GTest=TRUE \
    "${CMAKE_PREFIX_ARGS[@]}"
  # Build ONLY the atracdenc target, never "all": upstream's
  # man-atracdenc custom target (part of ALL) runs a hand-written
  # shell line with an UNQUOTED output path — it dies with
  # "No such file or directory" whenever the build folder's path
  # contains a space (GlitchedDot's first Step 3 build,
  # 2026-11-05: "DiscWrightPure 6" on /Volumes/NAS). We never
  # install, so the man page is dead weight anyway.
  cmake --build "$ENC_BUILD" --target atracdenc -j
  echo "$NEW_STAMP" > "$ENC_STAMP"
fi

APP="DiscWright.app"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp app/Info.plist "$APP/Contents/Info.plist"
cp "$ENC_BIN" "$APP/Contents/Resources/atracdenc"
cp app/AppIcon.icns "$APP/Contents/Resources/AppIcon.icns"
chmod +x "$APP/Contents/Resources/atracdenc"

echo "Compiling DiscWright (native core + SwiftUI face)..."
# -parse-as-library: the entry point is the @main attribute in
# app/DiscWrightApp.swift, not top-level code.
swiftc -O -parse-as-library \
  -framework SwiftUI -framework AppKit -framework AVFoundation \
  -framework UniformTypeIdentifiers \
  -o "$APP/Contents/MacOS/DiscWright" \
  core/*.swift app/*.swift

# Ad-hoc signature so the bundle is well-formed for local use.
codesign --force --deep -s - "$APP" 2>/dev/null || true

echo ""
echo "Done: $APP"
echo "Launch it with:  open DiscWright.app"
echo "(First launch: if macOS objects, right-click the app and choose Open.)"
