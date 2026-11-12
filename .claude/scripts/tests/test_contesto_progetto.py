# 2nd Brain Hero Mode · Copyright (c) 2026 Alessandro Pacifico (Pacibrand).
# Vedi LICENZA.md nella radice del vault.
"""Test autonomi dell'hook del contesto di progetto (hooks/project-context.py).

Niente pytest: si lancia con `python3 test_contesto_progetto.py`. Ogni prova costruisce un vault
finto in una cartella temporanea (con una copia di `brain_config.py` e un `brain.json` di prova)
e lancia l'hook come lo lancia Claude Code: JSON su stdin, `CLAUDE_PROJECT_DIR` sul vault finto.
Ultima riga: `N/M test passati`; codice 1 se qualcosa fallisce.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

QUI = Path(__file__).resolve().parent
HOOK = QUI.parent.parent / "hooks" / "project-context.py"
LETTORE = QUI.parent / "brain_config.py"
RADICE = Path(tempfile.mkdtemp(prefix="contesto-progetto-", dir=os.environ.get("TEST_TMPDIR")))

ESITI = []


def verifica(nome, condizione, dettaglio=""):
    ESITI.append(bool(condizione))
    print(("ok: %s" % nome) if condizione else ("FALLITO: %s %s" % (nome, dettaglio)))


def vault(nome, progetti, con_lettore=True):
    v = RADICE / nome
    (v / ".claude" / "scripts").mkdir(parents=True)
    (v / ".claude" / "config").mkdir(parents=True)
    if con_lettore:
        shutil.copy2(LETTORE, v / ".claude" / "scripts" / "brain_config.py")
    (v / ".claude" / "config" / "brain.json").write_text(
        json.dumps({"projects": progetti}), encoding="utf-8")
    return v


def progetto(v, path, metodo=None, readme=None, refs=None, skill=()):
    base = v / path
    (base / "references").mkdir(parents=True, exist_ok=True)
    if metodo is not None:
        (base / "references" / "metodo.md").write_text(metodo, encoding="utf-8")
    if readme is not None:
        (base / "README.md").write_text(readme, encoding="utf-8")
    for nome, testo in (refs or {}).items():
        (base / "references" / nome).write_text(testo, encoding="utf-8")
    for s in skill:
        (base / "skills" / s).mkdir(parents=True)
        (base / "skills" / s / "SKILL.md").write_text("---\nname: %s\n---\n" % s, encoding="utf-8")
    return base


def lancia(v, prompt, sessione="s1", ingresso=None, extra_env=None):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(v))
    env.pop("CLAUDE_INVOKED_BY", None)
    env.update(extra_env or {})
    dati = ingresso if ingresso is not None else json.dumps({"prompt": prompt, "session_id": sessione})
    r = subprocess.run([sys.executable, str(HOOK)], input=dati, capture_output=True,
                       text=True, env=env, timeout=20)
    contesto = ""
    if r.stdout.strip():
        try:
            contesto = json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]
        except (ValueError, KeyError, TypeError):
            contesto = "<<uscita non valida>>" + r.stdout
    return r.returncode, contesto


ALFA = {"id": "alfa", "path": "10-lavoro/cliente-alfa", "alias": ["cliente alfa", "alfa"]}
README_LOOP = """# Cliente Alfa

## 🔓 Loop aperti
- [ ] **Preventivo da mandare** entro venerdì
- [ ] 🔴 **Contratto da firmare**
- [x] **Chiuso da tempo**

## Altro
- [ ] **Non è un loop**
"""

try:
    # 1. Nominare il progetto carica metodo, loop, essenziali e skill.
    v = vault("base", [ALFA])
    progetto(v, ALFA["path"], metodo="# Metodo\nSi consegna sempre in PDF.",
             readme=README_LOOP, refs={"brand.md": "Tono diretto.", "_README.md": "guida"},
             skill=["alfa-preventivo", "alfa-report"])
    codice, ctx = lancia(v, "Dove siamo con Cliente Alfa?")
    verifica("esce con 0", codice == 0)
    verifica("metodo caricato", "Si consegna sempre in PDF." in ctx, ctx[:200])
    verifica("loop aperti: solo quelli aperti della sezione",
             "Preventivo da mandare" in ctx and "Chiuso da tempo" not in ctx and "Non è un loop" not in ctx)
    verifica("loop urgente per primo", ctx.find("Contratto da firmare") < ctx.find("Preventivo da mandare"))
    verifica("essenziale caricato, guida della cartella esclusa", "Tono diretto." in ctx and "guida" not in ctx)
    verifica("skill del progetto elencate", "`alfa-preventivo`, `alfa-report`" in ctx)

    # 2. Seconda menzione nella stessa sessione: niente. Sessione nuova: di nuovo.
    _, ctx2 = lancia(v, "e ancora alfa")
    verifica("una volta per sessione", ctx2 == "", ctx2[:100])
    _, ctx3 = lancia(v, "alfa", sessione="s2")
    verifica("sessione nuova ricarica", "Si consegna sempre in PDF." in ctx3)

    # 3. Solo parole intere, senza distinguere maiuscole e minuscole.
    _, ctx4 = lancia(v, "parliamo di alfabeto e alfa-beta", sessione="s3")
    verifica("nessun pezzo di parola", ctx4 == "", ctx4[:100])
    _, ctx5 = lancia(v, "CLIENTE ALFA va bene", sessione="s4")
    verifica("maiuscole indifferenti", "Contesto del progetto" in ctx5)

    # 4. Nessun messaggio pertinente, nessun output.
    _, ctx6 = lancia(v, "ciao, che tempo fa?", sessione="s5")
    verifica("messaggio senza progetti: silenzio", ctx6 == "")

    # 5. Alias assente: vale l'id. Due progetti nello stesso messaggio, in ordine di comparsa.
    beta = {"id": "beta", "path": "10-lavoro/beta"}
    v2 = vault("due", [ALFA, beta])
    progetto(v2, ALFA["path"], metodo="metodo alfa")
    progetto(v2, beta["path"], metodo="metodo beta")
    _, ctx7 = lancia(v2, "confronta beta con cliente alfa")
    verifica("alias assente: vale l'id", "metodo beta" in ctx7)
    verifica("due progetti in ordine", 0 <= ctx7.find("metodo beta") < ctx7.find("metodo alfa"))

    # 6. Tetto degli essenziali: oltre, solo il nome del file.
    v3 = vault("tetto", [ALFA])
    progetto(v3, ALFA["path"], refs={"corto.md": "breve", "lungo.md": "x" * 20000})
    _, ctx8 = lancia(v3, "alfa")
    verifica("metodo mancante detto in una riga", "non ha ancora `references/metodo.md`" in ctx8)
    verifica("file corto intero", "### Essenziale: `references/corto.md`\nbreve" in ctx8)
    verifica("file oltre il tetto solo per nome", "`references/lungo.md`" in ctx8 and "x" * 100 not in ctx8)

    # 7. Metodo troppo lungo: troncato con l'avviso.
    v4 = vault("metodo-lungo", [ALFA])
    progetto(v4, ALFA["path"], metodo="riga\n" * 4000)
    _, ctx9 = lancia(v4, "alfa")
    verifica("metodo troncato con avviso", "metodo troncato" in ctx9 and len(ctx9) < 13000, str(len(ctx9)))

    # 8. Casi che non devono mai rompere: servizio, ingresso rotto, config vuota o senza lettore,
    #    cartella del progetto inesistente.
    codice, ctx10 = lancia(v, "alfa", sessione="s6", extra_env={"CLAUDE_INVOKED_BY": "flush"})
    verifica("Claude di servizio: silenzio", codice == 0 and ctx10 == "")
    codice, ctx11 = lancia(v, None, ingresso="non è json")
    verifica("ingresso illeggibile: uscita 0 muta", codice == 0 and ctx11 == "")
    codice, ctx12 = lancia(v, None, ingresso="[1, 2]")
    verifica("ingresso di forma inattesa: uscita 0 muta", codice == 0 and ctx12 == "")
    v5 = vault("vuoto", [])
    codice, ctx13 = lancia(v5, "progetto esempio")
    verifica("nessun progetto configurato: uscita 0 muta", codice == 0 and ctx13 == "")
    v6 = vault("senza-lettore", [ALFA], con_lettore=False)
    progetto(v6, ALFA["path"], metodo="m")
    codice, ctx14 = lancia(v6, "alfa")
    verifica("lettore della config assente: uscita 0 muta", codice == 0 and ctx14 == "")
    v7 = vault("senza-cartella", [ALFA])
    codice, ctx15 = lancia(v7, "alfa")
    verifica("cartella del progetto inesistente: uscita 0 muta", codice == 0 and ctx15 == "")
    v8 = RADICE / "config-rotta"
    (v8 / ".claude" / "scripts").mkdir(parents=True)
    (v8 / ".claude" / "config").mkdir(parents=True)
    shutil.copy2(LETTORE, v8 / ".claude" / "scripts" / "brain_config.py")
    (v8 / ".claude" / "config" / "brain.json").write_text("{ rotto", encoding="utf-8")
    codice, ctx16 = lancia(v8, "alfa")
    verifica("brain.json rotto: uscita 0 muta", codice == 0 and ctx16 == "")

    # 9. Nessun trattino lungo nel contesto prodotto.
    verifica("nessun trattino lungo", chr(0x2014) not in ctx + ctx7 + ctx8 + ctx9)
finally:
    shutil.rmtree(RADICE, ignore_errors=True)

passati = sum(ESITI)
print("%d/%d test passati" % (passati, len(ESITI)))
sys.exit(0 if passati == len(ESITI) else 1)
