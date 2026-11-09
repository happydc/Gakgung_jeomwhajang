#!/usr/bin/env bash
# 웹 버전 사이트 조립: _site/ 에 화면 + 파이썬 파일 + 자산 + ezdxf 휠
set -euo pipefail
OUT="${1:-_site}"
rm -rf "$OUT"
mkdir -p "$OUT/assets/vendor" "$OUT/assets/fonts" "$OUT/wheels"
VER="$(git rev-parse --short HEAD 2>/dev/null || date +%s)"
sed "s/__VER__/$VER/" web/index.html > "$OUT/index.html"
cp web/web_api.py "$OUT/"
cp jeomhwajang_core.py jeomhwajang_3d.py jeomhwajang_gui.py jeomhwajang_preview.py "$OUT/"
cp assets/icon.png "$OUT/assets/"
cp assets/vendor/* "$OUT/assets/vendor/"
cp assets/fonts/* "$OUT/assets/fonts/"
python3 -m pip download -q ezdxf==1.4.2 --no-deps --only-binary=:all: --platform any --python-version 3.12 -d "$OUT/wheels"
touch "$OUT/.nojekyll"
ls -la "$OUT"
