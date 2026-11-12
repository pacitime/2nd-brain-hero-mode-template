#!/bin/zsh
# 2nd Brain Hero Mode · Copyright (c) 2026 Alessandro Pacifico (Pacibrand).
# Vedi LICENZA.md nella radice del vault.
# Trascrive un file audio (vocali Slack/WhatsApp: m4a, ogg, mp3, bin) in testo, in locale.
# Uso: trascrivi_audio.sh <file> [lingua, default it]
# Richiede: brew install whisper-cpp ffmpeg; modello in ~/.local/share/whisper-cpp/
# Su Slack il file si scarica con slack_read_file, che salva un .bin: va bene così com'è.
# Non scrive nulla nel vault: la trascrizione esce a schermo, l'audio non lascia il computer.
MODEL="$HOME/.local/share/whisper-cpp/ggml-large-v3-turbo.bin"

if [ -z "$1" ] || [ ! -f "$1" ]; then
  echo "Uso: trascrivi_audio.sh <file audio> [lingua, default it]" >&2
  exit 1
fi
for tool in ffmpeg whisper-cli; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "Manca $tool. Installa con: brew install whisper-cpp ffmpeg" >&2
    exit 1
  fi
done
if [ ! -f "$MODEL" ]; then
  echo "Manca il modello di trascrizione: $MODEL" >&2
  echo "Scarica ggml-large-v3-turbo.bin (modelli di whisper.cpp) e mettilo in quella cartella." >&2
  exit 1
fi

BASE="$(mktemp -t vocale)"
TMP="$BASE.wav"
ffmpeg -loglevel error -y -i "$1" -ar 16000 -ac 1 "$TMP" || { rm -f "$BASE" "$TMP"; exit 1; }
whisper-cli -m "$MODEL" -l "${2:-it}" -nt -np -f "$TMP" 2>/dev/null
rm -f "$BASE" "$TMP"
