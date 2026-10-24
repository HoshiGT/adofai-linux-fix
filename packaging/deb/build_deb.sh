#!/usr/bin/env bash
# ==============================================================================
# 构建 .deb 包 (Architecture: all)
# 产物: packaging/deb/build/adofai-linux-fix_<ver>_all.deb
# 仅需要 dpkg-deb; 包内容为 Python 脚本 + 预编译产物, 不在构建期编译。
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"

VERSION="1.1.0"
PKG="adofai-linux-fix"
MAINTAINER="HoshiGT <HoshiGT@users.noreply.github.com>"
HOMEPAGE="https://github.com/HoshiGT/adofai-linux-fix"
BUILD="$SCRIPT_DIR/build/$PKG"
APP="/usr/lib/$PKG"

if ! command -v dpkg-deb &>/dev/null; then
    echo "[-] Error: dpkg-deb not found." >&2
    exit 1
fi

rm -rf "$BUILD"
mkdir -p "$BUILD/DEBIAN" \
         "$BUILD$APP" \
         "$BUILD/usr/bin" \
         "$BUILD/usr/share/applications" \
         "$BUILD/usr/share/icons/hicolor/256x256/apps" \
         "$BUILD/usr/share/doc/$PKG"

# ---------------------------------------------------------------- 应用文件
cp "$ROOT_DIR/adofai_fix.py" "$ROOT_DIR/adofai_modmgr.py" "$BUILD$APP/"
cp -r "$ROOT_DIR/src" "$ROOT_DIR/scripts" "$ROOT_DIR/dist" "$BUILD$APP/"
find "$BUILD$APP" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
chmod -R a+rX "$BUILD$APP"

INSTALLED_SIZE=$(du -sk "$BUILD/usr" | cut -f1)

# ---------------------------------------------------------------- control
cat > "$BUILD/DEBIAN/control" <<EOF
Package: $PKG
Version: $VERSION
Section: games
Priority: optional
Architecture: all
Installed-Size: $INSTALLED_SIZE
Depends: python3 (>= 3.8), python3-gi, gir1.2-gtk-4.0, mono-runtime
Recommends: mono-devel, zip
Suggests: steam
Maintainer: $MAINTAINER
Homepage: $HOMEPAGE
Description: ADOFAI Linux native fix & UMM mod manager toolkit
 Toolkit for A DANCE OF FIRE AND ICE (冰与火之舞) on Linux / Steam Deck:
 drag-and-drop UMM mod manager GUI (GTK4, zh/en/ko), UMM assembly
 injector with backup/restore, shader-warmup crash fix mod, CJK font
 fix and environment diagnostics.
EOF

# ---------------------------------------------------------------- copyright
MIT_TEXT="Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the \"Software\"), to
deal in the Software without restriction, including without limitation the
rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
sell copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE."

cat > "$BUILD/usr/share/doc/$PKG/copyright" <<EOF
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: $PKG
Source: $HOMEPAGE

Files: *
Copyright: 2026 HoshiGT
License: MIT
$MIT_TEXT

Files: usr/lib/$PKG/dist/dnlib.dll
Copyright: Jonas Nyrup
License: MIT
 dnlib is MIT licensed; redistributed here because the injector binary
 resolves it next to the executable at runtime.
 (See above for the full MIT license text.)

License: MIT
$MIT_TEXT
EOF

# ---------------------------------------------------------------- 启动器
cat > "$BUILD/usr/bin/adofai-fix" <<EOF
#!/bin/sh
exec python3 $APP/adofai_fix.py "\$@"
EOF
cat > "$BUILD/usr/bin/adofai-modmgr" <<EOF
#!/bin/sh
exec python3 $APP/adofai_modmgr.py "\$@"
EOF
chmod 755 "$BUILD/usr/bin/adofai-fix" "$BUILD/usr/bin/adofai-modmgr"

# ---------------------------------------------------------------- 桌面入口
cat > "$BUILD/usr/share/applications/adofai-modmgr.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=ADOFAI Mod Manager
Name[zh_CN]=ADOFAI 模组管理器
Name[ko]=ADOFAI 모드 관리자
GenericName=UMM Mod Manager
Comment=Drag-and-drop UMM mod manager & injector for A DANCE OF FIRE AND ICE
Comment[zh_CN]=冰与火之舞 UMM 模组拖拽管理器与 UMM 注入器
Comment[ko]=A DANCE OF FIRE AND ICE용 UMM 모드 관리자 및 주입기
Exec=adofai-modmgr
Terminal=false
Categories=Game;Utility;
Keywords=adofai;umm;mod;模组;모드;
Icon=adofai-linux-fix
EOF

# ---------------------------------------------------------------- 图标
ICON_SRC="$SCRIPT_DIR/icon.png"
ICON_DST="$BUILD/usr/share/icons/hicolor/256x256/apps/adofai-linux-fix.png"
if [[ -f "$ICON_SRC" ]]; then
    cp "$ICON_SRC" "$ICON_DST"
else
    # 兜底: 现场生成 (需要 Pillow)
    python3 - "$ICON_DST" <<'PYEOF'
import sys
from PIL import Image, ImageDraw

S = 256
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# 深色圆角底
d.rounded_rectangle([8, 8, S - 8, S - 8], radius=48, fill=(34, 36, 44, 255))

# 左下冰蓝 / 右上火焰橙 的对角双色圆
cx, cy, r = S // 2, S // 2, 86
for i in range(r, 0, -1):
    t = i / r
    fire = (255, 120 + int(60 * (1 - t)), 30, 255)
    ice = (60, 150 + int(60 * (1 - t)), 255, 255)
    # 沿对角线过渡
    steps = 64
    for k in range(steps):
        a0 = k * 360 / steps
        a1 = (k + 1) * 360 / steps
        import math
        mid = math.radians((a0 + a1) / 2)
        w = (math.cos(mid) + 1) / 2  # 0..1 右上偏火
        col = tuple(int(fire[j] * w + ice[j] * (1 - w)) for j in range(3)) + (255,)
        d.pieslice([cx - i, cy - i, cx + i, cy + i], a0, a1, fill=col)

# 中央音符 (节奏游戏)
d.ellipse([cx - 46, cy + 12, cx - 2, cy + 56], fill=(255, 255, 255, 255))
d.ellipse([cx + 2, cy - 4, cx + 46, cy + 40], fill=(255, 255, 255, 255))
d.rectangle([cx - 8, cy - 60, cx - 2, cy + 34], fill=(255, 255, 255, 255))
d.rectangle([cx + 40, cy - 76, cx + 46, cy + 18], fill=(255, 255, 255, 255))
d.polygon([(cx - 8, cy - 60), (cx + 46, cy - 76), (cx + 46, cy - 62), (cx - 8, cy - 46)],
          fill=(255, 255, 255, 255))

img.save(sys.argv[1])
print("icon ->", sys.argv[1])
PYEOF
fi

# ---------------------------------------------------------------- 打包
OUT="$SCRIPT_DIR/build/${PKG}_${VERSION}_all.deb"
rm -f "$OUT"
dpkg-deb --build --root-owner-group "$BUILD" "$OUT"
dpkg-deb --info "$OUT" | head -12
echo "[+] $OUT"
