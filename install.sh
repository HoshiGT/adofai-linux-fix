#!/usr/bin/env bash
# ==============================================================================
# One-Click Installer for ADOFAI Linux Native Fix Toolkit
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_TOOL="$SCRIPT_DIR/adofai_fix.py"

if ! command -v python3 &>/dev/null; then
    echo "[-] Error: python3 is required to run the installer."
    exit 1
fi

chmod +x "$PYTHON_TOOL"

if [[ $# -eq 0 ]]; then
    python3 "$PYTHON_TOOL"
else
    python3 "$PYTHON_TOOL" "$@"
fi
