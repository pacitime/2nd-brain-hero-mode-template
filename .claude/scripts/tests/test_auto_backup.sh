#!/bin/bash
# 2nd Brain Hero Mode · Copyright (c) 2026 Alessandro Pacifico (Pacibrand).
# Vedi LICENZA.md nella radice del vault.
# Test di auto-backup.sh e cloud-sync.sh, su repository finti in una cartella temporanea
# (nessuna rete, il vault vero non viene toccato).
#   bash .claude/scripts/tests/test_auto_backup.sh
# Copre lo scenario dei due scrittori (la routine cloud pusha per prima, il Mac committa, il
# push verrebbe rifiutato non-fast-forward e il vault resterebbe fuori da GitHub in silenzio)
# e i livelli senza GitHub: cartella che non e' un repository, repository senza remote.
VAULT_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
SCRIPT="$VAULT_ROOT/.claude/scripts/auto-backup.sh"
CLOUD="$VAULT_ROOT/.claude/scripts/cloud-sync.sh"
TMP="$(mktemp -d)"; PASS=0; FAIL=0
# I test girano come sul computer: senza queste due variabili, che una sessione di Claude imposta.
unset CLAUDE_CODE_REMOTE CLAUDE_PROJECT_DIR
ck() { if [ "$2" = "$3" ]; then echo "  [OK ] $1"; PASS=$((PASS+1)); else echo "  [FAIL] $1 (atteso '$3', ottenuto '$2')"; FAIL=$((FAIL+1)); fi; }
have() { if [ -e "$1" ]; then echo si; else echo no; fi; }
in_origin() { if git -C "$TMP/origin.git" cat-file -e "main:$1" 2>/dev/null; then echo si; else echo no; fi; }

git init -q --bare -b main "$TMP/origin.git"
git clone -q "$TMP/origin.git" "$TMP/mac" 2>/dev/null
git clone -q "$TMP/origin.git" "$TMP/notturna" 2>/dev/null
for r in mac notturna; do git -C "$TMP/$r" config user.email t@t.t; git -C "$TMP/$r" config user.name "$r"; done
# come in un vault vero: il log del backup e' fuori da git, altrimenti ogni giro si
# auto-genererebbe una modifica da committare e "nessuna modifica" non capiterebbe mai.
printf '.claude/data/*\n' > "$TMP/mac/.gitignore"
echo base > "$TMP/mac/a.md"; git -C "$TMP/mac" add -A; git -C "$TMP/mac" commit -qm base
git -C "$TMP/mac" push -q origin main; git -C "$TMP/notturna" pull -q origin main

echo "[1] la notturna ha pushato per prima, il Mac ha lavoro locale"
echo notte > "$TMP/notturna/notte.md"; git -C "$TMP/notturna" add -A
git -C "$TMP/notturna" commit -qm "digestione notturna"; git -C "$TMP/notturna" push -q origin main
echo locale > "$TMP/mac/locale.md"
VAULT_DIR="$TMP/mac" bash "$SCRIPT" >/dev/null 2>&1
ck "push riuscito: 0 commit locali fuori da GitHub" "$(git -C "$TMP/mac" rev-list --count origin/main..HEAD)" "0"
ck "il lavoro del Mac e' su origin"                 "$(in_origin locale.md)" "si"
ck "il lavoro della notturna NON e' stato perso"    "$(in_origin notte.md)" "si"
ck "il file della notturna e' anche sul Mac"        "$(have "$TMP/mac/notte.md")" "si"

echo "[2] conflitto vero sullo stesso file -> annulla, non lascia il repo a meta'"
git -C "$TMP/notturna" pull -q --rebase origin main
echo "riga della notturna" > "$TMP/notturna/conteso.md"; git -C "$TMP/notturna" add -A
git -C "$TMP/notturna" commit -qm n2; git -C "$TMP/notturna" push -q origin main
echo "riga del mac" > "$TMP/mac/conteso.md"
VAULT_DIR="$TMP/mac" bash "$SCRIPT" >/dev/null 2>&1
ck "nessun rebase lasciato a meta' (merge)"  "$(have "$TMP/mac/.git/rebase-merge")" "no"
ck "nessun rebase lasciato a meta' (apply)"  "$(have "$TMP/mac/.git/rebase-apply")" "no"
ck "il conflitto e' scritto nel log"         "$(grep -c 'CONFLITTO col remoto' "$TMP/mac/.claude/data/backup.log")" "1"
ck "il lavoro locale non e' stato buttato"   "$(have "$TMP/mac/conteso.md")" "si"

echo "[3] niente da salvare -> non fa nulla"
VAULT_DIR="$TMP/mac" bash "$SCRIPT" >/dev/null 2>&1
ck "log dice 'nessuna modifica'" "$(grep '^\[' "$TMP/mac/.claude/data/backup.log" | tail -1 | grep -c 'nessuna modifica')" "1"

echo "[4] cartella che non e' un repository git -> esce pulito e non crea nulla"
mkdir -p "$TMP/senza-git"; echo nota > "$TMP/senza-git/nota.md"
out="$(VAULT_DIR="$TMP/senza-git" bash "$SCRIPT" 2>&1)"; rc=$?
ck "exit 0"                         "$rc" "0"
ck "nessun output a schermo"        "$out" ""
ck "non ha creato un repository"    "$(have "$TMP/senza-git/.git")" "no"
ck "non ha creato cartelle di log"  "$(have "$TMP/senza-git/.claude")" "no"

echo "[5] repository senza remote (GitHub non collegato) -> commit locale, niente push"
git init -q -b main "$TMP/solo"; git -C "$TMP/solo" config user.email t@t.t; git -C "$TMP/solo" config user.name solo
printf '.claude/data/*\n' > "$TMP/solo/.gitignore"; echo nota > "$TMP/solo/nota.md"
out="$(VAULT_DIR="$TMP/solo" bash "$SCRIPT" 2>&1)"; rc=$?
ck "exit 0"                             "$rc" "0"
ck "nessun output a schermo"            "$out" ""
ck "il commit locale c'e'"              "$(git -C "$TMP/solo" rev-list --count HEAD 2>/dev/null)" "1"
ck "il log dice che manca il remote"    "$(grep -c "nessun remote 'origin'" "$TMP/solo/.claude/data/backup.log")" "1"
VAULT_DIR="$TMP/solo" bash "$SCRIPT" >/dev/null 2>&1
ck "secondo giro senza modifiche: skip" "$(tail -1 "$TMP/solo/.claude/data/backup.log" | grep -c 'nessuna modifica')" "1"

echo "[6] remote appena creato e ancora vuoto -> primo push"
git init -q --bare -b main "$TMP/vuoto.git"
git -C "$TMP/solo" remote add origin "$TMP/vuoto.git"
echo altra > "$TMP/solo/altra.md"
VAULT_DIR="$TMP/solo" bash "$SCRIPT" >/dev/null 2>&1; rc=$?
ck "exit 0"                      "$rc" "0"
ck "il lavoro e' sul remote"     "$(if git -C "$TMP/vuoto.git" cat-file -e main:altra.md 2>/dev/null; then echo si; else echo no; fi)" "si"

echo "[7] repository su un ramo che non e' main -> non finge di aver salvato"
git -C "$TMP/solo" checkout -q -b prova
echo ramo > "$TMP/solo/ramo.md"
VAULT_DIR="$TMP/solo" bash "$SCRIPT" >/dev/null 2>&1; rc=$?
ck "exit 1"                       "$rc" "1"
ck "il log dice quale ramo"       "$(grep -c "ramo corrente e' 'prova'" "$TMP/solo/.claude/data/backup.log")" "1"
git -C "$TMP/solo" checkout -q main

echo "[8] il vault si trova anche senza VAULT_DIR (hook di sessione: CLAUDE_PROJECT_DIR)"
echo sessione > "$TMP/solo/sessione.md"
CLAUDE_PROJECT_DIR="$TMP/solo" bash "$SCRIPT" >/dev/null 2>&1
ck "commit fatto nel vault indicato" "$(git -C "$TMP/solo" log -1 --format=%s | grep -c '^auto-backup')" "1"

echo "[9] in una sessione cloud auto-backup non fa nulla (salva cloud-sync)"
echo cloud > "$TMP/solo/cloud.md"
CLAUDE_CODE_REMOTE=true VAULT_DIR="$TMP/solo" bash "$SCRIPT" >/dev/null 2>&1; rc=$?
ck "exit 0"                 "$rc" "0"
ck "nessun commit nuovo"    "$(git -C "$TMP/solo" status --porcelain | grep -c 'cloud.md')" "1"
git -C "$TMP/solo" add -A; git -C "$TMP/solo" commit -qm pulizia

echo "[10] cloud-sync.sh: fuori dal cloud, senza repository o senza remote -> muto"
out="$(cd "$TMP/senza-git" && echo '{}' | CLAUDE_PROJECT_DIR="$TMP/senza-git" bash "$CLOUD" 2>&1)"; rc=$?
ck "sul computer: exit 0 e nessun output"            "$rc|$out" "0|"
out="$(cd "$TMP/senza-git" && echo '{}' | CLAUDE_CODE_REMOTE=true CLAUDE_PROJECT_DIR="$TMP/senza-git" bash "$CLOUD" 2>&1)"; rc=$?
ck "cloud senza repository: exit 0 e nessun output"  "$rc|$out" "0|"
git init -q -b main "$TMP/cloud-solo"; git -C "$TMP/cloud-solo" config user.email t@t.t; git -C "$TMP/cloud-solo" config user.name c
echo x > "$TMP/cloud-solo/x.md"
out="$(echo '{}' | CLAUDE_CODE_REMOTE=true CLAUDE_PROJECT_DIR="$TMP/cloud-solo" bash "$CLOUD" 2>&1)"; rc=$?
ck "cloud senza remote: exit 0 e nessun output"      "$rc|$out" "0|"
ck "cloud senza remote: nessun commit creato"        "$(git -C "$TMP/cloud-solo" rev-list --count --all)" "0"

echo "[11] cloud-sync.sh: sessione cloud con remote -> il lavoro arriva su main"
git clone -q "$TMP/origin.git" "$TMP/telefono" 2>/dev/null
git -C "$TMP/telefono" config user.email c@c.c; git -C "$TMP/telefono" config user.name telefono
git -C "$TMP/telefono" checkout -q -b claude/sessione
echo dal-telefono > "$TMP/telefono/telefono.md"
out="$(echo '{}' | CLAUDE_CODE_REMOTE=true CLAUDE_PROJECT_DIR="$TMP/telefono" bash "$CLOUD" 2>&1)"; rc=$?
ck "exit 0 e nessun avviso"            "$rc|$out" "0|"
ck "il lavoro del telefono e' su main" "$(in_origin telefono.md)" "si"

echo "[12] lanciato senza variabili (launchd): il vault e' quello in cui sta lo script"
git init -q -b main "$TMP/launchd"; git -C "$TMP/launchd" config user.email t@t.t; git -C "$TMP/launchd" config user.name l
mkdir -p "$TMP/launchd/.claude/scripts"; cp "$SCRIPT" "$TMP/launchd/.claude/scripts/auto-backup.sh"
printf '.claude/data/*\n' > "$TMP/launchd/.gitignore"
(cd / && bash "$TMP/launchd/.claude/scripts/auto-backup.sh" >/dev/null 2>&1)
ck "commit fatto nel vault dello script" "$(git -C "$TMP/launchd" rev-list --count HEAD 2>/dev/null)" "1"

python3 -c "import shutil,sys; shutil.rmtree(sys.argv[1], ignore_errors=True)" "$TMP"
echo; echo "$PASS/$((PASS+FAIL)) test passati"; [ "$FAIL" -eq 0 ]
