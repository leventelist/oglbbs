#!/bin/bash
set -e

APP_NAME="oglbbs"
BUILD_DIR="build"
PYZ_FILE="${APP_NAME}.pyz"

echo "[+] Cleaning up..."
rm -rf "$BUILD_DIR" "$PYZ_FILE"

echo "[+] Creating build structure..."
mkdir -p "$BUILD_DIR"

echo "[+] Copying source files..."
cp *.py "$BUILD_DIR"/

echo "[+] Creating __main__.py..."
cat > "$BUILD_DIR"/__main__.py <<EOF
import $APP_NAME
$APP_NAME.main()
EOF

echo "[+] Installing dependencies into build dir..."
pip install --target "$BUILD_DIR" -r requirements.txt

python -m zipapp $BUILD_DIR/ -p '/usr/bin/env python3' -o $PYZ_FILE

echo "[+] Done. Run it with: python $PYZ_FILE"