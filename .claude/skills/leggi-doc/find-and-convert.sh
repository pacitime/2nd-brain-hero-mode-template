#!/usr/bin/env bash
# 2nd Brain Hero Mode · Copyright (c) 2026 Alessandro Pacifico (Pacibrand).
# Vedi LICENZA.md nella radice del vault.
# find-and-convert.sh: trova un documento e lo converte in testo leggibile.
# Uso:
#   find-and-convert.sh "<query|percorso>"     # cerca per nome (anche parziale) o path
#   find-and-convert.sh --latest               # prende il documento più recente
#
# Cerca in ~/Downloads, ~/Desktop e nel vault (cwd). Converte docx/doc/rtf/odt/html in .txt
# (via textutil, nativo macOS) e gli xlsx in Markdown (xlsx2md.py, qui accanto) nella
# scratchpad; pdf/txt/md/csv li lascia dove sono (si leggono diretti).
# Stampa in stdout una riga "READ: <percorso-da-leggere>" col file pronto, o "ERROR: ..." .
#
# Solo macOS: usa `textutil` e la sintassi BSD di `stat` (-f '%m %N').

# Niente `pipefail`: le pipeline `... | sort | head -1` chiudono il pipe in anticipo
# (SIGPIPE su sort) ed è voluto: non deve far fallire lo script.
set -eu

SCRATCH="${SCRATCHPAD_DIR:-/tmp}"
mkdir -p "$SCRATCH" 2>/dev/null || true

QUERY="${1:-}"
[ -z "$QUERY" ] && { echo "ERROR: manca la query (nome file o --latest)"; exit 1; }

# Zone di ricerca
SEARCH_DIRS=("$HOME/Downloads" "$HOME/Desktop" "$PWD")

find_latest() {
  find "${SEARCH_DIRS[@]}" -maxdepth 3 \
    \( -iname '*.docx' -o -iname '*.doc' -o -iname '*.pdf' -o -iname '*.rtf' -o -iname '*.odt' -o -iname '*.xlsx' -o -iname '*.csv' \) \
    -not -path '*/node_modules/*' -not -path '*/.git/*' 2>/dev/null \
    | xargs -I{} stat -f '%m %N' {} 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2-
}

find_by_query() {
  local q="$1"
  # 1) percorso esatto?
  if [ -f "$q" ]; then echo "$q"; return; fi
  # 2) match per sottostringa case-insensitive, più recente vince
  find "${SEARCH_DIRS[@]}" -maxdepth 3 -type f \
    \( -iname '*.docx' -o -iname '*.doc' -o -iname '*.pdf' -o -iname '*.rtf' -o -iname '*.odt' -o -iname '*.md' -o -iname '*.txt' -o -iname '*.html' -o -iname '*.xlsx' -o -iname '*.csv' \) \
    -not -path '*/node_modules/*' -not -path '*/.git/*' 2>/dev/null \
    | grep -i -- "$q" \
    | xargs -I{} stat -f '%m %N' {} 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2-
}

if [ "$QUERY" = "--latest" ]; then
  SRC="$(find_latest)"
else
  SRC="$(find_by_query "$QUERY")"
fi

[ -z "$SRC" ] && { echo "ERROR: nessun documento trovato per '$QUERY' in Downloads/Desktop/vault"; exit 2; }
[ ! -f "$SRC" ] && { echo "ERROR: file non accessibile: $SRC"; exit 2; }

echo "FOUND: $SRC"
ext="${SRC##*.}"; ext="$(echo "$ext" | tr '[:upper:]' '[:lower:]')"

case "$ext" in
  pdf|txt|md|csv)
    # leggibili direttamente dal tool Read
    echo "READ: $SRC"
    ;;
  docx|doc|rtf|odt|html|htm|wordml|webarchive)
    base="$(basename "$SRC")"; base="${base%.*}"
    # slug semplice per il nome di destinazione
    out="$SCRATCH/${base// /_}.txt"
    if textutil -convert txt "$SRC" -output "$out" 2>/dev/null; then
      echo "READ: $out"
    else
      echo "ERROR: conversione fallita per $SRC (formato $ext)"
      exit 3
    fi
    ;;
  xlsx)
    # xlsx = zip di XML: lo converto in Markdown con xlsx2md.py (solo stdlib, niente pip)
    base="$(basename "$SRC")"; base="${base%.*}"
    out="$SCRATCH/${base// /_}.md"
    if python3 "$(dirname "$0")/xlsx2md.py" "$SRC" --out "$out" >/dev/null 2>&1; then
      echo "READ: $out"
    else
      echo "ERROR: conversione xlsx fallita per $SRC (se è un vecchio .xls, riesporta in .xlsx o .csv)"
      exit 3
    fi
    ;;
  xls)
    echo "ERROR: .xls (formato binario vecchio) non gestito. Riesporta in .xlsx o .csv e riprova."
    exit 4
    ;;
  pptx|key|numbers|pages)
    echo "ERROR: formato $ext non supportato da textutil. Esporta in PDF o docx e riprova."
    exit 4
    ;;
  *)
    echo "ERROR: estensione non gestita: .$ext"
    exit 5
    ;;
esac
