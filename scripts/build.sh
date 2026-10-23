#!/usr/bin/env bash
# ==============================================================================
# Build Script for ADOFAI Linux Native Crash Fix & Enhancement Mod
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
SRC_FILE="$ROOT_DIR/src/LinuxCrashFix.cs"
DIST_DIR="$ROOT_DIR/dist/LinuxCrashFix"
OUTPUT_DLL="$DIST_DIR/LinuxCrashFix.dll"

# Potential ADOFAI installation paths
SEARCH_PATHS=(
    "${ADOFAI_PATH:-}"
    "${1:-}"
    "$HOME/.steam/debian-installation/steamapps/common/A Dance of Fire and Ice"
    "$HOME/.steam/steam/steamapps/common/A Dance of Fire and Ice"
    "$HOME/.local/share/Steam/steamapps/common/A Dance of Fire and Ice"
    "/var/lib/flatpak/app/com.valvesoftware.Steam/data/Steam/steamapps/common/A Dance of Fire and Ice"
)

GAME_DIR=""
for p in "${SEARCH_PATHS[@]}"; do
    if [[ -n "$p" && -d "$p/ADanceOfFireAndIce_Data/Managed" ]]; then
        GAME_DIR="$p"
        break
    elif [[ -n "$p" && -d "$p/A Dance of Fire and Ice_Data/Managed" ]]; then
        GAME_DIR="$p"
        break
    fi
done

if [[ -z "$GAME_DIR" ]]; then
    echo "[-] Error: Could not automatically detect ADOFAI Managed directory."
    echo "    Please specify the game path as an argument: ./build.sh \"/path/to/A Dance of Fire and Ice\""
    exit 1
fi

MANAGED="$GAME_DIR/ADanceOfFireAndIce_Data/Managed"
if [[ ! -d "$MANAGED" ]]; then
    MANAGED="$GAME_DIR/A Dance of Fire and Ice_Data/Managed"
fi

echo "[*] Using Game Managed directory: $MANAGED"

if ! command -v mcs &>/dev/null; then
    echo "[-] Error: Mono C# compiler ('mcs') not found."
    echo "    Please install mono (e.g., 'sudo apt install mono-mcs' or 'sudo pacman -S mono')."
    exit 1
fi

mkdir -p "$DIST_DIR"

echo "[*] Compiling $SRC_FILE..."
mcs -target:library \
    -nostdlib \
    -r:"$MANAGED/mscorlib.dll" \
    -r:"$MANAGED/netstandard.dll" \
    -r:"$MANAGED/System.dll" \
    -r:"$MANAGED/System.Core.dll" \
    -r:"$MANAGED/UnityModManager/0Harmony.dll" \
    -r:"$MANAGED/UnityModManager/UnityModManager.dll" \
    -r:"$MANAGED/UnityEngine.CoreModule.dll" \
    -r:"$MANAGED/UnityEngine.IMGUIModule.dll" \
    -r:"$MANAGED/UnityEngine.InputLegacyModule.dll" \
    -r:"$MANAGED/UnityEngine.dll" \
    -out:"$OUTPUT_DLL" \
    "$SRC_FILE"

echo "[+] Compilation successful: $OUTPUT_DLL ($(stat -c%s "$OUTPUT_DLL") bytes)"

# Create release zip
if command -v zip &>/dev/null; then
    cd "$ROOT_DIR/dist"
    ZIP_NAME="LinuxCrashFix-v1.0.0.zip"
    rm -f "$ZIP_NAME"
    zip -r "$ZIP_NAME" LinuxCrashFix/ >/dev/null
    echo "[+] Created UMM-ready package: $ROOT_DIR/dist/$ZIP_NAME"
fi
