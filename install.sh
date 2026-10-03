#!/bin/bash
# Sposta App - installazione per l'utente corrente
set -e

BIN_DIR="$HOME/.local/bin"
APP_DIR="$HOME/.local/share/applications"
DESKTOP="$APP_DIR/sposta-app.desktop"

mkdir -p "$BIN_DIR" "$APP_DIR"
cp "$(dirname "$0")/sposta-app.py" "$BIN_DIR/sposta-app.py"
chmod +x "$BIN_DIR/sposta-app.py"

# genera il .desktop con il percorso corretto di QUESTO utente
cat > "$DESKTOP" <<EOF
[Desktop Entry]
Name=Sposta App
Comment=Sposta le app Flatpak tra disco interno e SSD Predator
Exec=$BIN_DIR/sposta-app.py
Icon=drive-harddisk-usb
Terminal=false
Type=Application
Categories=Utility;
EOF

update-desktop-database "$APP_DIR" 2>/dev/null || true

echo "Installato! Cerca 'Sposta App' nel menu delle applicazioni."
echo "Avvio rapido per prova: sposta-app.py"
