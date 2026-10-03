#!/bin/bash
# Swichy SSD - installazione per l'utente corrente
set -e

BIN_DIR="$HOME/.local/bin"
APP_DIR="$HOME/.local/share/applications"
DESKTOP="$APP_DIR/swichyssd.desktop"

mkdir -p "$BIN_DIR" "$APP_DIR"
cp "$(dirname "$0")/sposta-app.py" "$BIN_DIR/sposta-app.py"
chmod +x "$BIN_DIR/sposta-app.py"

# genera il .desktop con il percorso corretto di QUESTO utente
cat > "$DESKTOP" <<EOF
[Desktop Entry]
Name=Swichy SSD
Comment=Sposta le app Flatpak tra disco interno e SSD esterno
Exec=$BIN_DIR/sposta-app.py
Icon=drive-removable-media
Terminal=false
Type=Application
Categories=Utility;
EOF

update-desktop-database "$APP_DIR" 2>/dev/null || true

echo "Installato! Cerca 'Swichy SSD' nel menu delle applicazioni."
echo "Se install.sh da' 'Permesso negato', lancia prima: chmod +x install.sh"
