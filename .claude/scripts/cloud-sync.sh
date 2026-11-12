#!/bin/bash
# 2nd Brain Hero Mode · Copyright (c) 2026 Alessandro Pacifico (Pacibrand).
# Vedi LICENZA.md nella radice del vault.
# cloud-sync.sh: salva su GitHub il lavoro di una sessione CLOUD (telefono, browser, routine)
# dopo OGNI risposta di Claude. Agganciato all'hook Stop in .claude/settings.json.
#
# Perche'. Dal telefono si lavora sul vault dalla scheda Code dell'app Claude: la sessione gira
# su una macchina virtuale che parte da un clone di GitHub e viene spenta dopo un po' di
# inattivita'. Quello che non e' su GitHub quando la macchina si spegne e' perso. Quindi:
#   - si salva a OGNI risposta, non a fine sessione: dal telefono la sessione non "finisce"
#     (chiudi l'app e basta), quindi SessionEnd non e' un appiglio affidabile;
#   - si scrive su `main`, non sul branch `claude/...` che la sessione cloud apre di default:
#     un lavoro parcheggiato su un branch non lo vedono ne' il computer ne' la routine notturna.
#     Il proxy GitHub del cloud lo consente: rifiuta solo cancellazioni e tag (documentazione di
#     Claude Code, "Configure cloud environments" > GitHub proxy > Push restrictions).
#
# Sul computer non fa nulla: li' salva auto-backup.sh. Il discriminante e' CLAUDE_CODE_REMOTE,
# che vale "true" solo nelle macchine cloud e mai in locale. Non fa nulla nemmeno se la cartella
# non e' un repository git o non ha un remote `origin`: senza GitHub non c'e' dove salvare.
#
# Conflitti: stessa regola del backup (vedi .claude/scripts/AUTOMAZIONI.md). Ci si allinea con
# rebase; se ci sono conflitti veri NON si fonde da script. Si mettono al sicuro i commit su un
# branch `cloud/da-riconciliare-...` (cosi' non muoiono con la macchina) e si chiede a Claude,
# nella sessione stessa, di riconciliare con una merge a tre vie tenendo entrambi i lati.
# Il computer all'avvio segnala i branch `cloud/` non fusi.
#
# Invariante: un salvataggio fallito non resta invisibile. Ogni fallimento esce come messaggio
# nella sessione (systemMessage), non in un log che nessuno legge.
#
# Exit: sempre 0. L'output, quando c'e', e' JSON per l'hook Stop.

[ "$CLAUDE_CODE_REMOTE" = "true" ] || exit 0

input="$(cat)"
cd "${CLAUDE_PROJECT_DIR:-$PWD}" || exit 0
gd="$(git rev-parse --git-dir 2>/dev/null)" || exit 0
git remote get-url origin >/dev/null 2>&1 || exit 0

# say systemMessage "testo"  -> avviso visibile, Claude si ferma
# say reason "testo"         -> Claude NON si ferma: riceve il testo e continua (riconciliazione)
say() {
  python3 -c '
import json, sys
k, v = sys.argv[1], sys.argv[2]
d = {"decision": "block", "reason": v} if k == "reason" else {"systemMessage": v}
print(json.dumps(d, ensure_ascii=False))' "$1" "$2"
}

# L'orologio e' quello della macchina cloud (di norma UTC): serve solo a dare un nome al commit.
ts="$(date '+%Y-%m-%d %H:%M')"

# Una merge o un rebase lasciati a meta' = Claude sta riconciliando: non toccare nulla.
if [ -d "$gd/rebase-merge" ] || [ -d "$gd/rebase-apply" ] || [ -f "$gd/MERGE_HEAD" ]; then
  say systemMessage "Vault: riconciliazione in corso, il salvataggio su GitHub riparte alla prossima risposta."
  exit 0
fi

git add -A
if ! git diff --cached --quiet; then
  if ! git commit -q -m "sessione cloud $ts" >/dev/null 2>&1; then
    say systemMessage "Vault: commit NON riuscito, le modifiche di questa risposta non sono salvate su GitHub."
    exit 0
  fi
fi

if ! git fetch -q origin main >/dev/null 2>&1; then
  say systemMessage "Vault: GitHub non raggiungibile, le modifiche NON sono ancora salvate. Riprovo alla prossima risposta."
  exit 0
fi

# Niente da salvare: ci si porta solo al passo con GitHub, cosi' una sessione lunga dal telefono
# vede anche quello che il computer o la routine notturna hanno scritto nel frattempo. Poi fine.
if [ "$(git rev-list --count origin/main..HEAD 2>/dev/null || echo 0)" -eq 0 ]; then
  git merge -q --ff-only origin/main >/dev/null 2>&1
  exit 0
fi

if [ "$(git rev-list --count HEAD..origin/main 2>/dev/null || echo 0)" -gt 0 ]; then
  if ! git rebase -q origin/main >/dev/null 2>&1; then
    git rebase --abort >/dev/null 2>&1
    safe="cloud/da-riconciliare-$(date '+%Y%m%d-%H%M%S')"
    if git push -q origin "HEAD:refs/heads/$safe" >/dev/null 2>&1; then
      where="al sicuro su GitHub nel branch $safe"
    else
      where="SOLO in questa sessione (anche il branch di sicurezza e' fallito)"
    fi
    if printf '%s' "$input" | grep -q '"stop_hook_active": *true'; then
      say systemMessage "Vault: conflitto con GitHub non risolto. Il lavoro e' $where. Va riconciliato (regole in .claude/scripts/AUTOMAZIONI.md)."
    else
      say reason "Salvataggio del vault su GitHub bloccato da un CONFLITTO: dall'ultima sincronia il computer o la routine notturna hanno modificato gli stessi file. Il lavoro di questa sessione e' $where. Riconcilia ora, senza chiedere il permesso (regole in .claude/scripts/AUTOMAZIONI.md): git merge origin/main, risolvi i conflitti tenendo entrambi i lati (fusione semantica, pezzo per pezzo), git commit, poi git push origin HEAD:main. Poi di' all'utente in una riga cosa hai fuso. Le contraddizioni vere fra i due lati restano a lui."
    fi
    exit 0
  fi
fi

if git push -q origin HEAD:main >/dev/null 2>&1; then
  exit 0
fi
# Qualcuno ha pushato fra il fetch e il push: un secondo giro, uno solo.
if git fetch -q origin main >/dev/null 2>&1 && git rebase -q origin/main >/dev/null 2>&1 \
   && git push -q origin HEAD:main >/dev/null 2>&1; then
  exit 0
fi
git rebase --abort >/dev/null 2>&1
say systemMessage "Vault: push su GitHub NON riuscito. Le modifiche restano in questa sessione e riprovo alla prossima risposta."
exit 0
