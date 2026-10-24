#!/usr/bin/env bash
# ==============================================================================
# 编译 UMM 注入器 (依赖游戏目录内的 dnlib.dll, 与 build.sh 同样的游戏检测逻辑)
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
SRC_FILE="$ROOT_DIR/src/UMMInjector.cs"
OUTPUT_EXE="$ROOT_DIR/dist/UMMInjector.exe"

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
        GAME_DIR="$p"; break
    elif [[ -n "$p" && -d "$p/A Dance of Fire and Ice_Data/Managed" ]]; then
        GAME_DIR="$p"; break
    fi
done

if [[ -z "$GAME_DIR" ]]; then
    echo "[-] Error: Could not automatically detect ADOFAI Managed directory."
    exit 1
fi

MANAGED="$GAME_DIR/ADanceOfFireAndIce_Data/Managed"
if [[ ! -d "$MANAGED" ]]; then
    MANAGED="$GAME_DIR/A Dance of Fire and Ice_Data/Managed"
fi

DNLIB="$MANAGED/UnityModManager/dnlib.dll"
if [[ ! -f "$DNLIB" ]]; then
    echo "[-] Error: dnlib.dll not found at $DNLIB (UMM 未安装, 需先获取 UMM 运行时)"
    exit 1
fi

if ! command -v mcs &>/dev/null; then
    echo "[-] Error: Mono C# compiler ('mcs') not found."
    exit 1
fi

# deb 安装到 /usr 后仓库目录只读: 构建产物落到用户数据目录
OUTROOT="$ROOT_DIR/dist"
if ! mkdir -p "$OUTROOT" 2>/dev/null || [[ ! -w "$OUTROOT" ]]; then
    OUTROOT="$HOME/.local/share/adofai-linux-fix/dist"
    mkdir -p "$OUTROOT"
fi
OUTPUT_EXE="$OUTROOT/UMMInjector.exe"

mcs -nostdlib -optimize+ \
    -r:"$MANAGED/mscorlib.dll" \
    -r:"$MANAGED/netstandard.dll" \
    -r:"$MANAGED/System.dll" \
    -r:"$MANAGED/System.Core.dll" \
    -r:"$MANAGED/System.Xml.dll" \
    -r:"$DNLIB" \
    -out:"$OUTPUT_EXE" \
    "$SRC_FILE"

# mono 运行时按 exe 同目录解析程序集引用
cp -f "$DNLIB" "$(dirname "$OUTPUT_EXE")/dnlib.dll"

echo "[+] Compiled: $OUTPUT_EXE ($(stat -c%s "$OUTPUT_EXE") bytes)"
