#!/bin/bash
# 2nd Brain Hero Mode · Copyright (c) 2026 Alessandro Pacifico (Pacibrand).
# Vedi LICENZA.md nella radice del vault.
# auto-backup.sh: salva il vault. Fa un commit git di cio' che e' cambiato e, se il vault e'
# collegato a GitHub (remote `origin`), lo spinge li'. Parte a fine sessione (hook SessionEnd)
# e, se l'hai attivato, ogni ora (vedi .claude/scripts/AUTOMAZIONI.md).
#
# Tre livelli, e a ognuno lo script fa solo quello che puo':
#   - nessun repository git  -> non fa nulla ed esce pulito (nemmeno un log);
#   - repository senza remote -> commit locale (la cronologia sul tuo computer), niente push;
#   - repository con `origin` -> commit, allineamento col remoto, push sul ramo `main`.
# Log in .claude/data/backup.log (fuori da git).

# launchd parte con un PATH minimo: aggiungo dove vivono git e gh (Homebrew compreso).
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

# In una sessione cloud (telefono, browser, routine) qui non c'e' nulla da fare: il salvataggio
# lo fa cloud-sync.sh a ogni risposta.
[ "$CLAUDE_CODE_REMOTE" = "true" ] && exit 0

# Dove sta il vault: VAULT_DIR (i test puntano a un repo finto), poi CLAUDE_PROJECT_DIR (hook
# di sessione), poi la posizione di questo script (launchd: <vault>/.claude/scripts/).
VAULT="${VAULT_DIR:-${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." 2>/dev/null && pwd)}}"
[ -n "$VAULT" ] && cd "$VAULT" 2>/dev/null || exit 1

# Nessun repository: il backup non e' attivo. Si guarda la cartella .git PRIMA di chiamare git:
# su un Mac senza gli strumenti da riga di comando, lanciare `git` fa comparire la finestra
# che propone di installarli, e chi non usa git non deve vederla a ogni fine sessione.
[ -e "$VAULT/.git" ] || exit 0
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0

mkdir -p "$VAULT/.claude/data"
LOG="$VAULT/.claude/data/backup.log"
ts="$(date '+%Y-%m-%d %H:%M')"

git add -A
if git diff --cached --quiet; then
  echo "[$ts] nessuna modifica: skip" >> "$LOG"
  exit 0
fi

if ! git commit -q -m "auto-backup $ts" >> "$LOG" 2>&1; then
  echo "[$ts] commit FALLITO (manca nome o email di git? vedi .claude/scripts/AUTOMAZIONI.md)" >> "$LOG"
  exit 1
fi

# Nessun remote: il vault vive solo su questo computer. Il commit locale e' fatto, fine.
if ! git remote get-url origin >/dev/null 2>&1; then
  echo "[$ts] commit locale OK, nessun remote 'origin': niente push (GitHub non collegato)" >> "$LOG"
  exit 0
fi

# Il push riguarda il ramo `main`: da un altro ramo spingerebbe un main fermo e direbbe "OK".
branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null)"
if [ "$branch" != "main" ]; then
  echo "[$ts] commit OK ma il ramo corrente e' '$branch', non 'main': niente push (vedi AUTOMAZIONI.md)" >> "$LOG"
  exit 1
fi

# Allinearsi PRIMA di pushare. Senza questo passo il push viene rifiutato non-fast-forward
# ogni volta che un altro scrittore (routine cloud notturna, sessione dal telefono) ha pushato
# per primo, e l'unica traccia sarebbe questo log, che sta fuori da git.
if ! git fetch -q origin main >> "$LOG" 2>&1; then
  # Remoto raggiungibile ma ancora senza `main` (repository GitHub appena creato, vuoto):
  # non c'e' nulla a cui allinearsi, si va dritti al primo push. Ogni altro errore e' rete o auth.
  git ls-remote --exit-code --heads origin main >/dev/null 2>&1
  if [ $? -ne 2 ]; then
    echo "[$ts] commit OK ma fetch FALLITO (rete o permessi) - riprovo al prossimo giro" >> "$LOG"
    exit 1
  fi
  echo "[$ts] remoto senza ramo main: primo push" >> "$LOG"
fi

behind="$(git rev-list --count HEAD..origin/main 2>/dev/null || echo 0)"
if [ "$behind" -gt 0 ]; then
  # --rebase e non merge: i commit di backup sono piccoli e locali, rimetterli sopra il lavoro
  # remoto tiene la storia lineare. Se ci sono conflitti veri NON si improvvisa: si annulla e
  # si lascia la riconciliazione a una sessione con un umano davanti.
  if ! git rebase -q origin/main >> "$LOG" 2>&1; then
    git rebase --abort >/dev/null 2>&1
    echo "[$ts] CONFLITTO col remoto ($behind commit): rebase annullato, vault NON su GitHub." >> "$LOG"
    echo "[$ts] -> serve riconciliazione a mano. L'avviso arriva a inizio sessione." >> "$LOG"
    exit 1
  fi
  echo "[$ts] allineato su origin/main ($behind commit tirati giu')" >> "$LOG"
fi

if git push -q origin main >> "$LOG" 2>&1; then
  echo "[$ts] commit + push OK" >> "$LOG"
else
  echo "[$ts] commit OK ma push FALLITO (controlla auth/rete)" >> "$LOG"
fi
