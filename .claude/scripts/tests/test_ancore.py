# 2nd Brain Hero Mode · Copyright (c) 2026 Alessandro Pacifico (Pacibrand).
# Vedi LICENZA.md nella radice del vault.
"""Test di protect-anchors.py, autonomi (niente pytest).

Lancia l'hook come sottoprocesso con un JSON finto su stdin e CLAUDE_PROJECT_DIR puntato su un
vault temporaneo. I casi PA-xxx sono le tabelle della specifica; dove decisioni.md cambia
l'esito, il caso segue la decisione e la nota lo dice («DECISIONE»). I casi N-xxx coprono le
regole nuove. Uscita 1 se qualcosa fallisce.

I nomi delle ancore sono composti a pezzi al momento dell'esecuzione: così questo file si può
maneggiare da shell (grep, python3 ...) senza far scattare l'hook installato nel vault.
"""

import json
import os
import subprocess
import sys
import tempfile

QUI = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.normpath(os.path.join(QUI, "..", "..", "hooks", "protect-anchors.py"))

# Nomi composti a pezzi apposta (vedi la docstring).
C = "CLA" + "UDE.md"
K = "CAPI" + "SALDI.md"
A = "ARCHI" + "TETTURA.md"

VAULT = os.path.realpath(tempfile.mkdtemp(prefix="vault-ancore-"))
FUORI = os.path.realpath(tempfile.mkdtemp(prefix="fuori-ancore-"))
os.makedirs(os.path.join(VAULT, "sub"), exist_ok=True)


def f(testo):
    """Sostituisce i segnaposto: {C} {K} {A} ancore, {V} vault, {O} cartella fuori dal vault."""
    return testo.format(C=C, K=K, A=A, V=VAULT, O=FUORI)


PASSA = ("passa", None)
RIGA = ("passa_con_riga", None)  # uscita 0, stdout vuoto, una riga su stderr


def CHIEDE(nome):
    return ("chiede", nome)


def BLOCCA(nome):
    return ("blocca", nome)


# (id, strumento, campi di tool_input, esito atteso, ambiente extra, nota)
# Per stdin grezzo: strumento None e i campi sono la stringa da mandare.
CASI = [
    # --- Edit e Write ---
    ("PA-001", "Edit", {"file_path": "{C}", "old_string": "a", "new_string": "x"}, CHIEDE(C), {}, "R4"),
    # DECISIONE: fuori dal vault non si applica (la specifica oggi chiede conferma).
    ("PA-002", "Edit", {"file_path": "/tmp/vault-finto/{C}", "old_string": "a"}, PASSA, {}, "fuori vault"),
    ("PA-002b", "Edit", {"file_path": "{V}/{C}", "old_string": "a"}, CHIEDE(C), {}, "assoluto nel vault"),
    # DECISIONE: fuori dal vault non si applica.
    ("PA-003", "Write", {"file_path": "/tmp/vault-finto/{K}", "content": "x"}, PASSA, {}, "fuori vault"),
    ("PA-003b", "Write", {"file_path": "{V}/{K}", "content": "x"}, CHIEDE(K), {}, "assoluto nel vault"),
    ("PA-004", "Edit", {"file_path": "{A}", "old_string": "a"}, CHIEDE(A), {}, "R4"),
    ("PA-005", "Write", {"file_path": "10-lavoro/p/{C}", "content": "testo"}, CHIEDE(C), {}, "qualunque cartella nel vault"),
    ("PA-006", "Edit", {"file_path": "./x/../{C}", "old_string": "a"}, CHIEDE(C), {}, "ultima componente"),
    ("PA-007", "Edit", {"file_path": "02-memoria/me.md", "new_string": "x"}, PASSA, {}, "R5"),
    ("PA-008", "Edit", {"file_path": "/tmp/vault-finto/02-memoria/me.md"}, PASSA, {}, "R5"),
    ("PA-009", "Write", {"file_path": "/tmp/vault-finto/audit-log.md"}, PASSA, {}, "R5"),
    ("PA-010", "Edit", {"file_path": "SOUL.md"}, PASSA, {}, "R5"),
    ("PA-011", "Edit", {"file_path": "MEMORY.md"}, PASSA, {}, "R5"),
    # DECISIONE: maiuscole e minuscole non contano.
    ("PA-012", "Edit", {"file_path": "claude.md"}, CHIEDE(C), {}, "minuscolo"),
    ("PA-013", "Edit", {"file_path": "Claude.md"}, CHIEDE(C), {}, "misto"),
    ("PA-014", "Edit", {"file_path": "{C}.bak"}, PASSA, {}, "R5"),
    ("PA-015", "Edit", {"file_path": "CLAUDE.local.md"}, PASSA, {}, "R5"),
    ("PA-016", "Edit", {"file_path": "MIO-{C}"}, PASSA, {}, "R5"),
    ("PA-017", "Edit", {"file_path": "{C}/"}, PASSA, {}, "ultima componente vuota"),
    ("PA-018", "Edit", {}, PASSA, {}, "file_path assente"),

    # --- Scappatoia e ingresso ---
    ("PA-019", "Edit", {"file_path": "{C}", "new_string": "x"}, PASSA, {"ALLOW_ANCHOR_EDIT": "1"}, "R1"),
    ("PA-020", "Bash", {"command": "echo x >> {C}"}, PASSA, {"ALLOW_ANCHOR_EDIT": "1"}, "R1"),
    ("PA-021", "Bash", {"command": "echo x >> {C}"}, BLOCCA(C), {"ALLOW_ANCHOR_EDIT": "true"}, "R1 solo con 1"),
    ("PA-022", "Edit", {"file_path": "{C}"}, CHIEDE(C), {"ALLOW_ANCHOR_EDIT": "0"}, "R1 solo con 1"),
    ("PA-023", None, "non json", PASSA, {"ALLOW_ANCHOR_EDIT": "1"}, "R1 prima di R2"),
    # DECISIONE: ingresso illeggibile = uscita 0 con una riga su stderr (la specifica: uscita 1).
    ("PA-024", None, "non json", RIGA, {}, "ingresso illeggibile"),
    ("PA-025", None, "", RIGA, {}, "stdin vuoto"),
    ("PA-026", None, "{}", PASSA, {}, "nessuno strumento"),
    # DECISIONE: tool_input nullo vale come vuoto (la specifica: errore).
    ("PA-027", None, '{"tool_name": "Edit", "tool_input": null}', PASSA, {}, "tool_input nullo"),

    # --- Altri strumenti ---
    ("PA-028", "Read", {"file_path": "{C}"}, PASSA, {}, "R6"),
    ("PA-029", "Grep", {"path": "{C}"}, PASSA, {}, "R6"),
    ("PA-030", "Glob", {"pattern": "{C}"}, PASSA, {}, "R6"),
    ("PA-031", "MultiEdit", {"file_path": "{C}"}, PASSA, {}, "R6 (oggi)"),
    ("PA-032", "NotebookEdit", {"notebook_path": "{C}"}, PASSA, {}, "R6 (oggi)"),

    # --- Bash: redirezione ---
    ("PA-033", "Bash", {"command": "echo x >> {C}"}, BLOCCA(C), {}, "R8"),
    ("PA-034", "Bash", {"command": "cat >> {C}"}, BLOCCA(C), {}, "R8"),
    # DECISIONE: fuori dal vault non si applica.
    ("PA-035", "Bash", {"command": "echo x > /tmp/vault-finto/{C}"}, PASSA, {}, "fuori vault"),
    ("PA-035b", "Bash", {"command": "echo x > {V}/{C}"}, BLOCCA(C), {}, "assoluto nel vault"),
    ("PA-036", "Bash", {"command": "echo x > ../{C}"}, BLOCCA(C), {"_cwd": "{V}/sub"}, "relativo, risolto nel vault"),
    ("PA-037", "Bash", {"command": "cat > {C} <<'EOF'\nciao\nEOF"}, BLOCCA(C), {}, "documento in linea"),
    ("PA-038", "Bash", {"command": "echo x >{C}"}, BLOCCA(C), {}, "senza spazio"),
    ("PA-039", "Bash", {"command": "echo x > '{C}'"}, BLOCCA(C), {}, "fra apici"),
    ("PA-040", "Bash", {"command": "echo x > \"./{K}\""}, BLOCCA(K), {}, "fra virgolette"),
    ("PA-041", "Bash", {"command": "cmd &> {C}"}, BLOCCA(C), {}, "&>"),
    ("PA-042", "Bash", {"command": "cmd 2> {C}"}, BLOCCA(C), {}, "2>"),
    ("PA-043", "Bash", {"command": "cmd >|{C}"}, BLOCCA(C), {}, ">|"),
    ("PA-044", "Bash", {"command": "echo x >\n{C}"}, BLOCCA(C), {}, "a capo"),
    ("PA-045", "Bash", {"command": "echo $(echo x > {C})"}, BLOCCA(C), {}, "sostituzione di comando"),
    # DECISIONE: nome esatto anche da shell.
    ("PA-046", "Bash", {"command": "echo x > {C}.bak"}, PASSA, {}, "nome esatto"),
    ("PA-047", "Bash", {"command": "echo x > MIO-{C}"}, PASSA, {}, "nome esatto"),
    # DECISIONE: citare il nome in un testo passa.
    ("PA-048", "Bash", {"command": "echo 'vedi -> {C}'"}, PASSA, {}, "freccia in un testo"),
    ("PA-049", "Bash", {"command": "git commit -m 'sposto regola > {C}'"}, PASSA, {}, "messaggio di commit"),
    ("PA-050", "Bash", {"command": "grep -c \"\" {C} > /tmp/conteggio.txt"}, PASSA, {}, "R8 non vale"),
    ("PA-051", "Bash", {"command": "cat {C} > /tmp/copia.md"}, PASSA, {}, "R8 non vale"),
    ("PA-052", "Bash", {"command": "cat {C} >> note.md"}, PASSA, {}, "R8 non vale"),
    ("PA-053", "Bash", {"command": "wc -l < {C}"}, PASSA, {}, "ingresso"),
    ("PA-054", "Bash", {"command": "diff <(cat a) {C}"}, PASSA, {}, "R8 non vale"),
    # DECISIONE: maiuscole e minuscole non contano.
    ("PA-055", "Bash", {"command": "echo x > claude.md"}, BLOCCA(C), {}, "minuscolo"),
    # DECISIONE: si bloccano le scritture (la specifica oggi le lascia passare).
    ("PA-056", "Bash", {"command": "cmd >| {C}"}, BLOCCA(C), {}, ">| con spazio"),
    ("PA-057", "Bash", {"command": "echo x > 'cartella con spazi/{C}'"}, BLOCCA(C), {}, "percorso con spazi"),

    # --- Bash: tee ---
    ("PA-058", "Bash", {"command": "echo x | tee -a {C}"}, BLOCCA(C), {}, "R9"),
    ("PA-059", "Bash", {"command": "echo x | tee {C}"}, BLOCCA(C), {}, "R9"),
    ("PA-060", "Bash", {"command": "echo x | tee -a -i ../{A}"}, BLOCCA(A), {"_cwd": "{V}/sub"}, "più opzioni"),
    ("PA-061", "Bash", {"command": "echo x | tee '{C}'"}, BLOCCA(C), {}, "fra apici"),
    ("PA-062", "Bash", {"command": "cat {C} | tee /tmp/a.txt"}, PASSA, {}, "ancora letta"),
    # DECISIONE: tee in ogni forma e posizione.
    ("PA-063", "Bash", {"command": "echo x | tee /tmp/a.txt {C}"}, BLOCCA(C), {}, "secondo file"),
    ("PA-064", "Bash", {"command": "echo x | tee --append {C}"}, BLOCCA(C), {}, "opzione lunga"),

    # --- Bash: modifica sul posto ---
    ("PA-065", "Bash", {"command": "sed -i '' 's/a/b/' {K}"}, BLOCCA(K), {}, "R10"),
    ("PA-066", "Bash", {"command": "sed -i.bak 's/a/b/' {C}"}, BLOCCA(C), {}, "R10"),
    ("PA-067", "Bash", {"command": "sed -E -i 's/a/b/' {C}"}, BLOCCA(C), {}, "R10"),
    ("PA-068", "Bash", {"command": "perl -i -pe 's/a/b/' {C}"}, BLOCCA(C), {}, "R10"),
    ("PA-069", "Bash", {"command": "ex -i x {C}"}, BLOCCA(C), {}, "R10"),
    ("PA-070", "Bash", {"command": "sed -n '1,5p' {C}"}, PASSA, {}, "stampa"),
    ("PA-071", "Bash", {"command": "sed 's/a/b/' {C}"}, PASSA, {}, "stampa"),
    # SCELTA: perl è un interprete come ruby; con un'ancora fra gli argomenti si blocca
    # (decisione: «un interprete ... con un'ancora fra gli argomenti resta bloccato»).
    ("PA-072", "Bash", {"command": "perl -ne 'print' {C}"}, BLOCCA(C), {}, "perl interprete"),
    # DECISIONE: perl -pi e sed --in-place bloccati.
    ("PA-073", "Bash", {"command": "perl -pi -e 's/a/b/' {C}"}, BLOCCA(C), {}, "perl -pi"),
    ("PA-074", "Bash", {"command": "sed --in-place 's/a/b/' {C}"}, BLOCCA(C), {}, "sed --in-place"),
    # SCELTA: awk -i inplace è una scrittura, come sed -i (principio della decisione).
    ("PA-075", "Bash", {"command": "awk -i inplace '{{print}}' {C}"}, BLOCCA(C), {}, "awk sul posto"),
    # DECISIONE: && e a capo separano i comandi.
    ("PA-076", "Bash", {"command": "sed -i 's/a/b/' altro.md && cat {C}"}, PASSA, {}, "&& separa"),
    ("PA-077", "Bash", {"command": "sed -i 's/a/b/' altro.md\ncat {C}"}, PASSA, {}, "a capo separa"),
    ("PA-078", "Bash", {"command": "sed -i 's/a/b/' altro.md; cat {C}"}, PASSA, {}, "; separa"),
    ("PA-079", "Bash", {"command": "sed -i 's/a/b/' altro.md | cat {C}"}, PASSA, {}, "| separa"),

    # --- Bash: spostare, copiare, cancellare ---
    ("PA-080", "Bash", {"command": "rm {A}"}, BLOCCA(A), {}, "R11"),
    ("PA-081", "Bash", {"command": "mv /tmp/nuovo.md {C}"}, BLOCCA(C), {}, "R11"),
    ("PA-082", "Bash", {"command": "mv {C} vecchio.md"}, BLOCCA(C), {}, "R11"),
    ("PA-083", "Bash", {"command": "cp /tmp/x.md {K}"}, BLOCCA(K), {}, "R11"),
    # DECISIONE: copiarla altrove è una lettura.
    ("PA-084", "Bash", {"command": "cp {C} /tmp/copia.md"}, PASSA, {}, "cp sorgente"),
    ("PA-085", "Bash", {"command": "git rm {C}"}, BLOCCA(C), {}, "git rm"),
    ("PA-086", "Bash", {"command": "git mv {C} x.md"}, BLOCCA(C), {}, "git mv"),
    ("PA-087", "Bash", {"command": "truncate -s 0 {C}"}, BLOCCA(C), {}, "R11"),
    ("PA-088", "Bash", {"command": "shred {C}"}, BLOCCA(C), {}, "R11"),
    ("PA-089", "Bash", {"command": "dd of={C}"}, BLOCCA(C), {}, "dd of="),
    ("PA-090", "Bash", {"command": "patch {C} fix.diff"}, BLOCCA(C), {}, "R11"),
    # DECISIONE: && e a capo separano i comandi.
    ("PA-091", "Bash", {"command": "rm a.md && cat {C}"}, PASSA, {}, "&& separa"),
    ("PA-092", "Bash", {"command": "rm a.md\ncat {C}"}, PASSA, {}, "a capo separa"),
    ("PA-093", "Bash", {"command": "rm a.md; cat {C}"}, PASSA, {}, "; separa"),
    ("PA-094", "Bash", {"command": "cat {C} && rm a.md"}, PASSA, {}, "nome prima"),
    ("PA-095", "Bash", {"command": "MV a.md {C}"}, PASSA, {}, "comando in maiuscolo (oggi)"),
    ("PA-096", "Bash", {"command": "scp {C} host:"}, PASSA, {}, "scp in lettura"),
    # DECISIONE: rsync, ln -sf, git checkout --, git restore, curl -o bloccati.
    ("PA-097", "Bash", {"command": "rsync a.md {C}"}, BLOCCA(C), {}, "rsync"),
    ("PA-098", "Bash", {"command": "ln -sf a.md {C}"}, BLOCCA(C), {}, "ln -sf"),
    ("PA-099", "Bash", {"command": "git checkout -- {C}"}, BLOCCA(C), {}, "git checkout --"),
    ("PA-100", "Bash", {"command": "git restore {C}"}, BLOCCA(C), {}, "git restore"),
    ("PA-101", "Bash", {"command": "curl -o {C} https://x"}, BLOCCA(C), {}, "curl -o"),

    # --- Bash: interpreti ---
    ("PA-102", "Bash", {"command": "python3 -c \"open('{C}','w').write('x')\""}, BLOCCA(C), {}, "R12"),
    ("PA-103", "Bash", {"command": "python3 script.py {C}"}, BLOCCA(C), {}, "script con l'ancora"),
    ("PA-104", "Bash", {"command": "python -c \"print(open('{C}').read())\""}, BLOCCA(C), {}, "interprete: resta bloccato"),
    ("PA-105", "Bash", {"command": "python3.11 x.py {C}"}, BLOCCA(C), {}, "versione"),
    ("PA-106", "Bash", {"command": "node -e \"require('fs').writeFileSync('{C}','x')\""}, BLOCCA(C), {}, "node"),
    ("PA-107", "Bash", {"command": "ruby -e \"File.write('{A}','x')\""}, BLOCCA(A), {}, "ruby"),
    # DECISIONE: && separa i comandi.
    ("PA-108", "Bash", {"command": "python3 x.py && cat {C}"}, PASSA, {}, "&& separa"),
    ("PA-109", "Bash", {"command": "python3 x.py; cat {C}"}, PASSA, {}, "; separa"),
    ("PA-110", "Bash", {"command": "python3 x.py | grep {C}"}, PASSA, {}, "| separa"),
    ("PA-111", "Bash", {"command": "cat {C} | python3 x.py"}, PASSA, {}, "nome prima"),
    ("PA-112", "Bash", {"command": "python3 .claude/scripts/route_calls.py"}, PASSA, {}, "nessuna ancora"),
    # SCELTA: perl, bash con uno script e osascript sono interpreti o script lanciati con
    # un'ancora fra gli argomenti: bloccati come python3 (la specifica oggi li lascia passare).
    ("PA-113", "Bash", {"command": "perl -e 'open(F,q(+<{C}))'"}, BLOCCA(C), {}, "perl -e"),
    ("PA-114", "Bash", {"command": "bash scrivi.sh {C}"}, BLOCCA(C), {}, "script"),
    ("PA-115", "Bash", {"command": "osascript -e 'x {C}'"}, BLOCCA(C), {}, "osascript"),

    # --- Bash: letture e lavoro normale ---
    ("PA-116", "Bash", {"command": "cat {C}"}, PASSA, {}, "lettura"),
    ("PA-117", "Bash", {"command": "grep -n \"regola\" {C}"}, PASSA, {}, "lettura"),
    ("PA-118", "Bash", {"command": "head -20 {A}"}, PASSA, {}, "lettura"),
    ("PA-119", "Bash", {"command": "git status --short {C}"}, PASSA, {}, "R7"),
    ("PA-120", "Bash", {"command": "git log --oneline -5 {C}"}, PASSA, {}, "R7"),
    ("PA-121", "Bash", {"command": "git diff {C}"}, PASSA, {}, "R7"),
    ("PA-122", "Bash", {"command": "git add {C}"}, PASSA, {}, "R7"),
    ("PA-123", "Bash", {"command": "wc -l {C} {K} {A}"}, PASSA, {}, "R7"),
    ("PA-124", "Bash", {"command": "touch {C}"}, PASSA, {}, "R7"),
    ("PA-125", "Bash", {"command": "chmod 444 {C}"}, PASSA, {}, "R7"),
    ("PA-126", "Bash", {"command": "ls"}, PASSA, {}, "normale"),
    ("PA-127", "Bash", {"command": ""}, PASSA, {}, "vuoto"),
    ("PA-128", "Bash", {}, PASSA, {}, "assente"),

    # --- Regole nuove (decisioni.md) ---
    ("N-001", "Edit", {"file_path": "{V}/sub/claude.MD"}, CHIEDE(C), {}, "maiuscole indifferenti, sottocartella"),
    ("N-002", "Edit", {"file_path": "{C}"}, PASSA, {"_cwd": "{O}"}, "relativo, ma la cartella di lavoro è fuori dal vault"),
    ("N-003", "Bash", {"command": "cd {O} && echo x > {C}"}, PASSA, {}, "dopo cd fuori dal vault"),
    ("N-004", "Bash", {"command": "cd {O} && cd {V} && echo x > {C}"}, BLOCCA(C), {}, "cd di ritorno nel vault"),
    ("N-005", "Bash", {"command": "rm a.md || cat {C}"}, PASSA, {}, "|| separa"),
    ("N-006", "Bash", {"command": "rm {K} {C}"}, BLOCCA(K), {}, "più ancore: si nomina la prima"),
    ("N-007", "Bash", {"command": "echo x > {C}; rm {A}"}, BLOCCA(C), {}, "più ancore: la prima"),
    ("N-008", "Bash", {"command": "wget -O {C} https://x"}, BLOCCA(C), {}, "wget -O"),
    ("N-009", "Bash", {"command": "curl --output {C} https://x"}, BLOCCA(C), {}, "curl --output"),
    ("N-010", "Bash", {"command": "curl -sSLo {C} https://x"}, BLOCCA(C), {}, "curl, opzioni unite"),
    ("N-011", "Bash", {"command": "curl -O https://x/{C}"}, BLOCCA(C), {}, "curl -O col nome dell'ancora"),
    ("N-012", "Bash", {"command": "install a.md {C}"}, BLOCCA(C), {}, "install"),
    ("N-013", "Bash", {"command": "cp /tmp/x/{C} ."}, BLOCCA(C), {}, "cp verso la cartella del vault"),
    ("N-014", "Bash", {"command": "cp {C} /tmp/"}, PASSA, {}, "cp verso cartella fuori"),
    ("N-015", "Bash", {"command": "cp -t sub /tmp/x/{A}"}, BLOCCA(A), {}, "cp -t"),
    ("N-016", "Bash", {"command": "git restore --staged {C}"}, PASSA, {}, "solo l'indice"),
    ("N-017", "Bash", {"command": "git restore --staged --worktree {C}"}, BLOCCA(C), {}, "anche il file"),
    ("N-018", "Bash", {"command": "git -C {O} rm {C}"}, PASSA, {}, "git -C fuori dal vault"),
    ("N-019", "Bash", {"command": "bash -c \"echo x > {C}\""}, BLOCCA(C), {}, "bash -c analizzato"),
    ("N-020", "Bash", {"command": "bash -c \"cat {C}\""}, PASSA, {}, "bash -c in lettura"),
    ("N-021", "Bash", {"command": "python3 - <<'EOF'\nopen('{C}','w').write('x')\nEOF"}, BLOCCA(C), {}, "codice in un documento in linea"),
    ("N-022", "Bash", {"command": "cat > nota.md <<'EOF'\nrm {C}\nEOF"}, PASSA, {}, "testo di un documento in linea"),
    ("N-023", "Bash", {"command": "bash <<'EOF'\nrm {C}\nEOF"}, BLOCCA(C), {}, "shell che esegue un documento in linea"),
    ("N-024", "Bash", {"command": "find . -name {C} -delete"}, BLOCCA(C), {}, "find -delete"),
    ("N-025", "Bash", {"command": "find . -name {C}"}, PASSA, {}, "find in lettura"),
    ("N-026", "Bash", {"command": "echo \"$(rm {C})\""}, BLOCCA(C), {}, "sostituzione fra virgolette"),
    ("N-027", "Bash", {"command": "sed -i 's/a/b/' {O}/{C}"}, PASSA, {}, "sed -i fuori dal vault"),
    ("N-028", "Bash", {"command": "echo x > /tmp/vault-finto/{C}"}, BLOCCA(C), {"_novault": "1"}, "vault ignoto: prudenza"),
    ("N-029", "Edit", {"file_path": "/tmp/vault-finto/{C}"}, CHIEDE(C), {"_novault": "1"}, "vault ignoto: prudenza"),
    ("N-030", None, "[1, 2]", PASSA, {}, "JSON che non è un oggetto"),
    ("N-031", None, '{"tool_name": "Bash", "tool_input": ["x"]}', PASSA, {}, "tool_input lista"),
    ("N-032", None, '{"tool_name": "Bash", "tool_input": {"command": 5}}', PASSA, {}, "command non testo"),
    ("N-033", None, '{"tool_name": "Edit", "tool_input": {"file_path": null}}', PASSA, {}, "file_path nullo"),
    ("N-034", "Bash", {"command": "cat {C} 2>&1 | head"}, PASSA, {}, "2>&1 non è un file"),
    ("N-035", "Bash", {"command": "echo x 2>&1 > {C}"}, BLOCCA(C), {}, "redirezione dopo 2>&1"),
    ("N-036", "Bash", {"command": "ln -s {C} /tmp/collegamento"}, PASSA, {}, "ln con l'ancora come bersaglio"),
    ("N-037", "Bash", {"command": "scp host:x {C}"}, BLOCCA(C), {}, "scp verso l'ancora"),
    ("N-038", "Bash", {"command": "rsync -av {C} host:/x"}, PASSA, {}, "rsync verso remoto"),
    ("N-039", "Bash", {"command": "echo x | sudo tee {C}"}, BLOCCA(C), {}, "dietro sudo"),
    ("N-040", "Bash", {"command": "exec 3<> {C}"}, BLOCCA(C), {}, "<> apre in scrittura"),
    ("N-041", "Bash", {"command": "python3 -c \"print(open('{O}/{C}').read())\""}, PASSA, {}, "interprete su percorso fuori dal vault"),
    ("N-042", "Bash", {"command": "echo x > Capisaldi.MD"}, BLOCCA(K), {}, "messaggio col nome canonico"),
    ("N-043", "Bash", {"command": "xargs rm {C} < lista.txt"}, BLOCCA(C), {}, "dietro xargs"),
    ("N-044", "Bash", {"command": "echo '{C}' > /tmp/x.txt"}, PASSA, {}, "nome citato e scritto altrove"),
    ("N-045", "Bash", {"command": "git checkout main"}, PASSA, {}, "git checkout senza ancore"),
    ("N-046", "Bash", {"command": "(cd sub && rm ../{C})"}, BLOCCA(C), {}, "sottoshell"),
    ("N-047", "Bash", {"command": "echo x > `echo {C}`"}, BLOCCA(C), {}, "bersaglio calcolato che nomina l'ancora"),
    ("N-048", "Bash", {"command": "echo x > \"$HOME/{C}\""}, BLOCCA(C), {}, "percorso con variabile: prudenza"),
]


def esegui(caso):
    ident, strumento, campi, atteso, extra, _ = caso
    env = dict(os.environ)
    env.pop("ALLOW_ANCHOR_EDIT", None)
    env["CLAUDE_PROJECT_DIR"] = VAULT
    dati_extra = {}
    for chiave, valore in extra.items():
        if chiave == "_cwd":
            dati_extra["cwd"] = f(valore)
        elif chiave == "_novault":
            env.pop("CLAUDE_PROJECT_DIR", None)
        else:
            env[chiave] = valore
    if strumento is None:
        stdin = campi.encode("utf-8")
    else:
        ingresso = {k: f(v) if isinstance(v, str) else v for k, v in campi.items()}
        dati = {"tool_name": strumento, "tool_input": ingresso}
        dati.update(dati_extra)
        stdin = json.dumps(dati).encode("utf-8")
    r = subprocess.run([sys.executable, HOOK], input=stdin, capture_output=True, env=env,
                       cwd=VAULT, timeout=20)
    return r.returncode, r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace")


def verifica(caso, codice, out, err):
    tipo, nome = caso[3]
    if tipo == "passa":
        return codice == 0 and out == "" and err == ""
    if tipo == "passa_con_riga":
        return codice == 0 and out == "" and err.strip() != "" and err.strip().count("\n") == 0
    if tipo == "chiede":
        if codice != 0 or err != "":
            return False
        try:
            hso = json.loads(out)["hookSpecificOutput"]
        except Exception:
            return False
        return (hso.get("hookEventName") == "PreToolUse"
                and hso.get("permissionDecision") == "ask"
                and nome in hso.get("permissionDecisionReason", ""))
    if tipo == "blocca":
        return codice == 2 and out == "" and nome in err
    return False


def statici():
    """Controlli sul sorgente: intestazione e nessun trattino lungo."""
    risultati = []
    trattino = chr(0x2014)
    for percorso in (HOOK, os.path.abspath(__file__)):
        with open(percorso, encoding="utf-8") as fh:
            testo = fh.read()
        righe = testo.splitlines()
        nome = os.path.basename(percorso)
        risultati.append(("S-intestazione " + nome,
                          righe[0].startswith("# 2nd Brain Hero Mode · Copyright (c) 2026")
                          and righe[1] == "# Vedi LICENZA.md nella radice del vault."))
        risultati.append(("S-trattino " + nome, trattino not in testo))
    return risultati


def main():
    passati = 0
    totale = 0
    for caso in CASI:
        totale += 1
        try:
            codice, out, err = esegui(caso)
            ok = verifica(caso, codice, out, err)
        except Exception as errore:
            ok, codice, out, err = False, None, "", repr(errore)
        if ok:
            passati += 1
        else:
            print("FALLITO {} ({}): atteso {}, uscita {}, stdout {!r}, stderr {!r}".format(
                caso[0], caso[5], caso[3], codice, out[:200], err[:200]))
    for nome, ok in statici():
        totale += 1
        if ok:
            passati += 1
        else:
            print("FALLITO " + nome)
    print("{}/{} test passati".format(passati, totale))
    return 0 if passati == totale else 1


if __name__ == "__main__":
    sys.exit(main())
