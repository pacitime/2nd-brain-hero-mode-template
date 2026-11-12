#!/bin/bash
# 2nd Brain Hero Mode · Copyright (c) 2026 Alessandro Pacifico (Pacibrand).
# Vedi LICENZA.md nella radice del vault.
# Tiene sveglio il Mac, e acceso lo schermo, mentre Claude Code lavora.
#   start (UserPromptSubmit): avvia caffeinate -d -i per questa sessione
#   keep  (PreToolUse, SubagentStart): lo riaccende se manca. Serve agli agenti in
#         background: il turno principale è finito (Stop) ma loro lavorano ancora, e
#         ogni loro tool call passa di qui (il PreToolUse scatta anche nei subagenti)
#   stop  (Stop): toglie il blocco pieno e lascia 10 minuti di margine solo-sistema
#         (lo schermo si spegne, il Mac no), per coprire i silenzi fra una tool call e
#         l'altra degli agenti in background
#   off   (StopFailure, SessionEnd): spegne tutto
# -d tiene acceso lo schermo: con lo schermo spento il Mac sembra in stop anche mentre
# lavora. Contro: finché una chat lavora lo schermo non si blocca da solo.
# caffeinate muore da solo se si chiude Claude Code (-w) o dopo 4 ore (-t),
# così un turno interrotto con Esc non tiene sveglio il Mac all'infinito.
# Fuori da macOS (sessioni cloud) non fa nulla.

command -v caffeinate >/dev/null 2>&1 || exit 0

input=$(cat)
sid=$(printf '%s' "$input" | jq -r '.session_id // empty' 2>/dev/null)

# Il processo di Claude Code: il primo antenato che non sia una shell.
trova_owner() {
  owner=$PPID
  for _ in 1 2 3 4 5; do
    name=$(basename "$(ps -o comm= -p "$owner" 2>/dev/null)" | tr -d '-')
    case "$name" in
      sh|bash|zsh|dash) owner=$(ps -o ppid= -p "$owner" 2>/dev/null | tr -d ' ') ;;
      *) break ;;
    esac
  done
  [ -n "$owner" ] && [ "$owner" -gt 1 ] 2>/dev/null
}

if [ -z "$sid" ]; then trova_owner || exit 0; sid=$owner; fi

dir="${TMPDIR:-/tmp}/claude-keep-awake"
mkdir -p "$dir"
pidfile="$dir/$sid.pid"   # "<pid> <modo>", modo = pieno | margine

# Un keep alla volta: le tool call parallele non devono lanciare due caffeinate.
lock="$pidfile.lock"
find "$lock" -maxdepth 0 -mmin +1 -exec rmdir {} \; 2>/dev/null
for _ in 1 2 3 4 5 6 7 8 9 10; do
  mkdir "$lock" 2>/dev/null && break
  [ "$1" = keep ] && exit 0
  sleep 0.1
done
trap 'rmdir "$lock" 2>/dev/null' EXIT

modo_attivo() {
  [ -f "$pidfile" ] || return 1
  read -r pid modo < "$pidfile"
  [ "$(basename "$(ps -o comm= -p "$pid" 2>/dev/null)")" = caffeinate ] || return 1
  echo "${modo:-vecchio}"
}

spegni() {
  modo_attivo >/dev/null && kill "$pid" 2>/dev/null
  rm -f "$pidfile"
}

avvia() {
  trova_owner || exit 0
  case "$1" in
    pieno)   nohup caffeinate -d -i -t 14400 -w "$owner" >/dev/null 2>&1 & ;;
    margine) nohup caffeinate -i -t 600 -w "$owner" >/dev/null 2>&1 & ;;
  esac
  echo "$! $1" > "$pidfile"
}

case "$1" in
  start) spegni; avvia pieno ;;
  keep)  [ "$(modo_attivo)" = pieno ] || { spegni; avvia pieno; } ;;
  stop)  spegni; avvia margine ;;
  off)   spegni ;;
esac
exit 0
