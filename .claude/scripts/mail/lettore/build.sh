#!/bin/bash
# 2nd Brain Hero Mode · Copyright (c) 2026 Alessandro Pacifico (Pacibrand).
# Vedi LICENZA.md nella radice del vault.
# Costruisce LettorePosta.app (vedi lettore.applescript) in .claude/data/mail-sync/, gitignorata:
# il binario resta sul Mac, il sorgente e' versionato qui.
#
# Il permesso «controllare Mail» e' legato all'app cosi' com'e' firmata: ricostruirla lo fa
# chiedere di nuovo (una volta, con l'utente davanti al Mac). Quindi non si ricostruisce se esiste gia':
# per ricostruirla, togli prima l'app a mano. Va ricostruita anche quando cambiano pull, sent o
# read.applescript, perche' l'app ne contiene una copia.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
MAIL="$(dirname "$HERE")"
VAULT="$(cd "$MAIL/../../.." && pwd)"
APP="$VAULT/.claude/data/mail-sync/LettorePosta.app"

if [ -e "$APP" ]; then
  echo "LettorePosta.app esiste gia': $APP"
  echo "Per ricostruirla toglila a mano (poi macOS richiedera' il permesso su Mail)."
  exit 1
fi

mkdir -p "$(dirname "$APP")"
osacompile -o "$APP" "$HERE/lettore.applescript"
mkdir -p "$APP/Contents/Resources/lettore"
cp "$MAIL/pull.applescript" "$MAIL/sent.applescript" "$MAIL/read.applescript" "$APP/Contents/Resources/lettore/"

PL="$APP/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Set :CFBundleIdentifier com.secondbrain.lettore-posta" "$PL" 2>/dev/null \
  || /usr/libexec/PlistBuddy -c "Add :CFBundleIdentifier string com.secondbrain.lettore-posta" "$PL"
/usr/libexec/PlistBuddy -c "Add :LSUIElement bool true" "$PL" 2>/dev/null \
  || /usr/libexec/PlistBuddy -c "Set :LSUIElement true" "$PL"
USO="Legge la posta in sola lettura per il giro quotidiano dei loop del vault."
/usr/libexec/PlistBuddy -c "Set :NSAppleEventsUsageDescription $USO" "$PL" 2>/dev/null \
  || /usr/libexec/PlistBuddy -c "Add :NSAppleEventsUsageDescription string $USO" "$PL"

codesign --force --deep -s - "$APP"
echo "Costruita: $APP"
