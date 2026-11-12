# 2nd Brain Hero Mode · Copyright (c) 2026 Alessandro Pacifico (Pacibrand).
# Vedi LICENZA.md nella radice del vault.
"""Test autonomi dell'hook di apertura (session-start-context.py).

Niente pytest: si lancia con `python3 test_apertura.py`. Lavora solo in cartelle
temporanee (radice scelta con la variabile TEST_TMPDIR, se c'e'), usa remoti git locali
(repository nudi) e nessuna rete reale. Ultima riga: `N/M test passati`; codice 1 se
qualcosa fallisce.
"""

import datetime
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

QUI = Path(__file__).resolve().parent
HOOK = QUI.parent.parent / "hooks" / "session-start-context.py"
PYTHON = sys.executable

RADICE_PROVE = Path(tempfile.mkdtemp(prefix="apertura-", dir=os.environ.get("TEST_TMPDIR")))

# Identita' git solo per questo processo e i suoi figli; nessuna config globale.
os.environ.update({
    "GIT_AUTHOR_NAME": "Prova", "GIT_AUTHOR_EMAIL": "prova@example.invalid",
    "GIT_COMMITTER_NAME": "Prova", "GIT_COMMITTER_EMAIL": "prova@example.invalid",
    "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
})
for variabile in ("CLAUDE_INVOKED_BY", "CLAUDE_PROJECT_DIR"):
    os.environ.pop(variabile, None)

ESITI = []


def verifica(nome, condizione, dettaglio=""):
    ESITI.append((nome, bool(condizione)))
    if not condizione:
        print("FALLITO: %s %s" % (nome, dettaglio))
    else:
        print("ok: %s" % nome)


def carica_modulo():
    spec = importlib.util.spec_from_file_location("apertura_%d" % len(ESITI), str(HOOK))
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


M = carica_modulo()
GIOVEDI = datetime.date(2026, 11, 12)
VENERDI = datetime.date(2026, 11, 13)
M._oggi = lambda: GIOVEDI

_contatore = [0]


def nuova_cartella(nome):
    _contatore[0] += 1
    cartella = RADICE_PROVE / ("%02d-%s" % (_contatore[0], nome))
    cartella.mkdir(parents=True)
    return cartella


def scrivi(radice, relativo, testo):
    percorso = Path(radice) / relativo
    percorso.parent.mkdir(parents=True, exist_ok=True)
    percorso.write_text(testo, encoding="utf-8")
    return percorso


def git(cartella, *argomenti):
    r = subprocess.run(["git", "-C", str(cartella)] + list(argomenti),
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if r.returncode != 0:
        raise RuntimeError("git %s: %s" % (" ".join(argomenti), r.stdout.decode()))
    return r.stdout.decode().strip()


def commit_file(cartella, relativo, testo, messaggio="c"):
    scrivi(cartella, relativo, testo)
    git(cartella, "add", "-A")
    git(cartella, "commit", "-q", "-m", messaggio)


def remoto_e_cloni(nome):
    """Repository nudo con un commit su main, e due cloni: il vault e un altro scrittore."""
    base = nuova_cartella(nome)
    nudo = base / "remoto.git"
    git(base, "init", "-q", "--bare", "-b", "main", str(nudo))
    semina = base / "semina"
    git(base, "init", "-q", "-b", "main", str(semina))
    commit_file(semina, "base.md", "base\n")
    git(semina, "remote", "add", "origin", str(nudo))
    git(semina, "push", "-q", "origin", "main")
    vault = base / "vault"
    altro = base / "altro"
    git(base, "clone", "-q", str(nudo), str(vault))
    git(base, "clone", "-q", str(nudo), str(altro))
    return nudo, vault, altro


def con_ambiente(radice, invocatore=None):
    os.environ["CLAUDE_PROJECT_DIR"] = str(radice)
    if invocatore is None:
        os.environ.pop("CLAUDE_INVOKED_BY", None)
    else:
        os.environ["CLAUDE_INVOKED_BY"] = invocatore


def esegui_hook(radice, invocatore=None, stdin_testo='{"hook_event_name":"SessionStart"}',
                path_extra=None):
    ambiente = dict(os.environ)
    ambiente["CLAUDE_PROJECT_DIR"] = str(radice)
    ambiente.pop("CLAUDE_INVOKED_BY", None)
    if invocatore is not None:
        ambiente["CLAUDE_INVOKED_BY"] = invocatore
    if path_extra:
        ambiente["PATH"] = str(path_extra) + os.pathsep + ambiente.get("PATH", "")
    inizio = time.monotonic()
    r = subprocess.run([PYTHON, str(HOOK)], input=stdin_testo.encode(), env=ambiente,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    return r, time.monotonic() - inizio


def pezzi(contesto):
    return contesto.split(M.SEPARATORE)


CODA_ESEMPIO = """# Coda

## In attesa

<!--
### [AAAA-MM-GG] <tipo: decisione|lezione|fatto> → <destinazione>
**Proposta:** <testo>
-->

"""

CODA_UNO = CODA_ESEMPIO + """### [2030-01-10] fatto → wiki globale
**Proposta:** una cosa da ricordare
**Fonte:** sessione chat 2030-01-10
**Stato:** da rivedere

---

## Promossi (storico)

### [2030-01-02] fatto → wiki globale
"""


# --------------------------------------------------------------------------- git

def test_git():
    # 1: in pari
    _, vault, altro = remoto_e_cloni("pari")
    verifica("1 clone in pari: vuoto", M.sync_with_remote(vault) == "")

    # 2-3: indietro di 1
    commit_file(altro, "nuovo.md", "dal telefono\n")
    git(altro, "push", "-q", "origin", "main")
    msg = M.sync_with_remote(vault)
    verifica("2 indietro di 1: allineato + 1 commit", "allineato" in msg and "1 commit" in msg, msg)
    verifica("3 file dell'altro clone ora presente", (vault / "nuovo.md").exists())

    # 4-6: divergenti
    _, vault, altro = remoto_e_cloni("divergenti")
    commit_file(altro, "remoto.md", "r\n")
    git(altro, "push", "-q", "origin", "main")
    commit_file(vault, "locale.md", "l\n")
    msg = M.sync_with_remote(vault)
    verifica("4 divergenti: DIVERGENTI", "DIVERGENTI" in msg, msg)
    verifica("5 divergenti: nessuna fusione", not (vault / "remoto.md").exists())
    verifica("6 divergenti: backup orario continua a fallire",
             "backup orario continua a fallire" in msg)
    verifica("6b divergenti: i due numeri", "1 commit che GitHub non ha" in msg and "ne ha 1" in msg, msg)
    verifica("6c nessun trattino lungo", "\u2014" not in msg)

    # 7-8: solo avanti
    _, vault, _ = remoto_e_cloni("avanti")
    commit_file(vault, "locale.md", "l\n")
    msg = M.sync_with_remote(vault)
    verifica("7 solo avanti: non ancora su GitHub", "non ancora su GitHub" in msg, msg)
    verifica("8 solo avanti: niente DIVERGENTI", "DIVERGENTI" not in msg)

    # 9-12
    vuota = nuova_cartella("non-repo")
    verifica("9 non repo: sync vuoto", M.sync_with_remote(vuota) == "")
    verifica("10 non repo: cloud vuoto", M.unmerged_cloud_branches(vuota) == "")
    solo = nuova_cartella("senza-remote")
    git(solo, "init", "-q", "-b", "main")
    commit_file(solo, "a.md", "a\n")
    verifica("11 senza remote: sync vuoto", M.sync_with_remote(solo) == "")
    verifica("12 senza remote: cloud vuoto", M.unmerged_cloud_branches(solo) == "")

    # 25: remoto irraggiungibile (percorso che non esiste)
    _, vault, _ = remoto_e_cloni("irraggiungibile")
    git(vault, "remote", "set-url", "origin", str(RADICE_PROVE / "non-esiste.git"))
    verifica("25 remoto irraggiungibile: sync vuoto", M.sync_with_remote(vault) == "")
    verifica("25b remoto irraggiungibile: cloud vuoto", M.unmerged_cloud_branches(vault) == "")
    scrivi(vault, "CAPISALDI.md", "principi\n")
    con_ambiente(vault)
    ctx = M.build_context()
    verifica("25c remoto irraggiungibile: il resto esce",
             "## Oggi" in ctx and "## Capisaldi" in ctx and "Allineamento" not in ctx, ctx[:300])

    # 26: indietro di 2 con modifica locale che impedisce l'avanzamento
    _, vault, altro = remoto_e_cloni("ff-bloccato")
    commit_file(altro, "base.md", "base cambiata 1\n")
    commit_file(altro, "base.md", "base cambiata 2\n")
    git(altro, "push", "-q", "origin", "main")
    scrivi(vault, "base.md", "modifica locale non salvata\n")
    msg = M.sync_with_remote(vault)
    verifica("26 ff bloccato: avviso col numero 2", "indietro di 2 commit" in msg, msg)
    verifica("26b ff bloccato: risposta di git riportata",
             "base.md" in msg or "overwritten" in msg, msg)
    verifica("26c ff bloccato: file locale intatto",
             (vault / "base.md").read_text() == "modifica locale non salvata\n")
    verifica("26d ff bloccato: HEAD fermo", git(vault, "rev-list", "--count", "HEAD") == "1")

    # 27-29: rami cloud
    nudo, vault, altro = remoto_e_cloni("cloud")
    verifica("27a nessun ramo cloud: vuoto", M.unmerged_cloud_branches(vault) == "")
    git(altro, "checkout", "-q", "-b", "cloud/da-riconciliare-2030-01-10")
    commit_file(altro, "cloud.md", "dal cloud\n")
    git(altro, "push", "-q", "origin", "cloud/da-riconciliare-2030-01-10")
    msg = M.unmerged_cloud_branches(vault)
    verifica("27 ramo cloud fuori da main: avviso con 1 ramo",
             "1 ramo" in msg and "origin/cloud/da-riconciliare-2030-01-10" in msg, msg)
    git(altro, "checkout", "-q", "main")
    git(altro, "merge", "-q", "--ff-only", "cloud/da-riconciliare-2030-01-10")
    git(altro, "push", "-q", "origin", "main")
    verifica("28 ramo fuso in main: nessun avviso", M.unmerged_cloud_branches(vault) == "")
    git(altro, "checkout", "-q", "-b", "cloud/altro-2030-01-11")
    commit_file(altro, "cloud2.md", "x\n")
    git(altro, "push", "-q", "origin", "cloud/altro-2030-01-11")
    verifica("29a secondo ramo visto", "cloud/altro-2030-01-11" in M.unmerged_cloud_branches(vault))
    git(altro, "push", "-q", "origin", "--delete", "cloud/altro-2030-01-11")
    verifica("29 ramo cancellato sul remoto: nessun avviso", M.unmerged_cloud_branches(vault) == "")
    verifica("29b riferimento locale ripulito",
             "cloud/altro" not in git(vault, "for-each-ref", "refs/remotes/origin/cloud/"))


def test_git_mai_eseguito():
    """24 e 53: un git finto sul PATH lascia una traccia se viene lanciato."""
    finto = nuova_cartella("git-finto")
    traccia = finto / "git-chiamato"
    script = finto / "git"
    script.write_text("#!/bin/sh\necho \"$@\" >> '%s'\nexit 1\n" % traccia)
    script.chmod(0o755)
    vault = nuova_cartella("senza-git")
    scrivi(vault, "CAPISALDI.md", "principi\n")
    r, _ = esegui_hook(vault, path_extra=finto)
    verifica("24 senza .git: git mai eseguito", not traccia.exists())
    verifica("24b senza .git: contesto uscito", r.returncode == 0 and b"Capisaldi" in r.stdout)
    # controllo che il finto funzioni: con .git presente viene chiamato
    (vault / ".git").mkdir()
    esegui_hook(vault, path_extra=finto)
    verifica("24c (controllo) con .git il git finto viene chiamato", traccia.exists())
    traccia.unlink()

    # 53: caricamento come modulo, con .git presente e stdin pieno
    codice = (
        "import importlib.util, sys\n"
        "s = importlib.util.spec_from_file_location('h', %r)\n"
        "m = importlib.util.module_from_spec(s); s.loader.exec_module(m)\n"
        "resto = sys.stdin.read()\n"
        "sys.stderr.write('RESTO=' + resto)\n" % str(HOOK))
    ambiente = dict(os.environ, CLAUDE_PROJECT_DIR=str(vault),
                    PATH=str(finto) + os.pathsep + os.environ["PATH"])
    r = subprocess.run([PYTHON, "-c", codice], input=b"dati-evento", env=ambiente,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    verifica("53 modulo: nessuna stampa", r.stdout == b"", r.stdout)
    verifica("53b modulo: stdin non letto", b"RESTO=dati-evento" in r.stderr, r.stderr)
    verifica("53c modulo: git non chiamato", not traccia.exists())


# --------------------------------------------------------------------------- contesto

def test_contesto_base():
    vuoto = nuova_cartella("vault-vuoto")
    con_ambiente(vuoto)
    ctx = M.build_context()
    verifica("13 vault vuoto: ## Oggi", "## Oggi" in ctx)
    verifica("14 vault vuoto: niente Capisaldi/Chi e'/Giro posta",
             "## Capisaldi" not in ctx and "## Chi e'" not in ctx and "Giro posta" not in ctx)
    verifica("33 data in italiano", ctx == "## Oggi\n\ngiovedi 12 novembre 2026", repr(ctx))

    # 19 e 23: come programma, con stdin valido, vuoto, non JSON
    for nome, ingresso in (("json", '{"a":1}'), ("vuoto", ""), ("non-json", "%%% non json")):
        r, _ = esegui_hook(vuoto, stdin_testo=ingresso)
        try:
            dati = json.loads(r.stdout.decode())
            interno = dati["hookSpecificOutput"]
            ok = (list(dati) == ["hookSpecificOutput"]
                  and sorted(interno) == ["additionalContext", "hookEventName"]
                  and interno["hookEventName"] == "SessionStart"
                  and interno["additionalContext"].startswith("## Oggi\n\n")
                  and M.SEPARATORE not in interno["additionalContext"])
        except Exception as e:
            ok = False
        verifica("19/23 programma, stdin %s: un solo JSON con la sola data" % nome,
                 ok and r.returncode == 0 and r.stderr == b"", (r.stdout, r.stderr))

    # 20-21 e guard (decisioni): niente uscita
    for chi in ("flush", "mail-sync", "guard"):
        r, _ = esegui_hook(vuoto, invocatore=chi)
        verifica("20/21 CLAUDE_INVOKED_BY=%s: uscita 0, nessun carattere" % chi,
                 r.returncode == 0 and r.stdout == b"" and r.stderr == b"")

    # 32 / 30 / 31: venerdi
    verifica("32 non venerdi: nessun promemoria", "Revisione settimanale" not in ctx)
    scrivi(vuoto, "02-memoria/PROMOTE-QUEUE.md", CODA_ESEMPIO + "\n".join(
        "### [2030-01-%02d] fatto → x\n**Proposta:** p\n" % g for g in (3, 4, 5)))
    M._oggi = lambda: VENERDI
    try:
        ctx = M.build_context()
        primo = pezzi(ctx)[0]
        verifica("30 venerdi: primo pezzo e' il promemoria con 3",
                 "Revisione settimanale" in primo and " 3 candidati" in primo, primo)
        verifica("30b venerdi: c'e' anche il pezzo coda",
                 "coda promote: 3 in attesa, il piu' vecchio dal 2030-01-03" in ctx)
        verifica("30c promemoria non contiene diciture riservate",
                 all(d not in primo for d in ("## Oggi", "coda promote", "Giro posta",
                                              "## Chi e'", "## Capisaldi")))
        scrivi(vuoto, "02-memoria/PROMOTE-QUEUE.md", CODA_ESEMPIO)
        ctx = M.build_context()
        verifica("31 venerdi coda vuota: promemoria con 0, niente coda promote",
                 pezzi(ctx)[0].count(" 0 candidati") == 1 and "coda promote" not in ctx, ctx)
        verifica("31b venerdi: data", "venerdi 13 novembre 2026" in ctx)
    finally:
        M._oggi = lambda: GIOVEDI


def test_coda():
    v = nuova_cartella("coda")
    con_ambiente(v)
    verifica("36 coda assente: 0", M.count_promote_candidates(v) == 0)
    verifica("36b coda assente: nessun pezzo", "coda promote" not in M.build_context())
    scrivi(v, "02-memoria/PROMOTE-QUEUE.md", CODA_ESEMPIO + "\n## Promossi (storico)\n")
    verifica("15 solo esempio: 0", M.count_promote_candidates(v) == 0)
    verifica("16 solo esempio: niente coda promote", "coda promote" not in M.build_context())
    scrivi(v, "02-memoria/PROMOTE-QUEUE.md", CODA_UNO)
    verifica("17 un candidato vero: 1", M.count_promote_candidates(v) == 1)
    verifica("18 dicitura della coda",
             "coda promote: 1 in attesa, il piu' vecchio dal 2030-01-10" in M.build_context())
    scrivi(v, "02-memoria/PROMOTE-QUEUE.md", "## In attesa\n\n" + "".join(
        "### [%s] lezione → y\n\n" % d for d in ("2030-03-01", "2030-01-15", "2030-02-01")))
    ctx = M.build_context()
    verifica("34 tre candidati, il piu' vecchio",
             "coda promote: 3 in attesa, il piu' vecchio dal 2030-01-15" in ctx)
    scrivi(v, "02-memoria/PROMOTE-QUEUE.md", "## in attesa\n\n### [2030-01-10] fatto\n")
    verifica("35 sezione in minuscolo riconosciuta", M.count_promote_candidates(v) == 1)
    scrivi(v, "02-memoria/PROMOTE-QUEUE.md",
           "# Coda\n\n### [2030-01-10] fatto\n\n## Promossi\n\n### [2030-01-02] fatto\n")
    verifica("coda senza sezione In attesa: 0 (decisioni)", M.count_promote_candidates(v) == 0)
    scrivi(v, "02-memoria/PROMOTE-QUEUE.md",
           "## In attesa\n\n### [2030-13-45] data finta\n#### [2030-01-01] livello 4\n"
           "<!--\n### [2030-01-05] dentro un commento\n-->\n### [2030-01-06] vero\n")
    verifica("coda: data impossibile, livello 4 e commento non contano",
             M.count_promote_candidates(v) == 1)


def test_documenti_e_appunti():
    v = nuova_cartella("documenti")
    con_ambiente(v)
    scrivi(v, "CAPISALDI.md", "")
    verifica("39 capisaldi vuoto: nessun pezzo", "## Capisaldi" not in M.build_context())
    scrivi(v, "CAPISALDI.md", "\n\n  principi fermi  \n\n")
    scrivi(v, "02-memoria/SOUL.md", "sono l'assistente\n")
    ctx = M.build_context()
    verifica("capisaldi: testo senza spazi in testa e coda",
             "## Capisaldi: i principi che non cambiano (`CAPISALDI.md`)\n\nprincipi fermi" in ctx)
    verifica("37 SOUL senza status: active: niente pezzo", "sono l'assistente" not in ctx)
    scrivi(v, "02-memoria/SOUL.md", "<!-- status: active -->\nsono l'assistente\n")
    verifica("38 SOUL attivo: pezzo col testo", "sono l'assistente" in M.build_context())
    (v / "ARCHITETTURA.md").write_bytes(b"\xff\xfe non utf8 \xc3")
    ctx = M.build_context()
    verifica("documento non UTF-8: quel pezzo manca, il resto esce",
             "Architettura" not in ctx and "## Capisaldi" in ctx)

    verifica("42 nessun appunto: niente pezzo", "Appunti giornalieri" not in ctx)
    ieri = (GIOVEDI - datetime.timedelta(days=1)).isoformat()
    scrivi(v, "01-daily/%s.md" % ieri, "\n".join("ieri %d" % i for i in range(1, 41)) + "\n")
    ctx = M.build_context()
    blocco = pezzi(ctx)[-1]
    verifica("41 solo ieri: ultime 30 con avviso",
             "registro di ieri" in blocco and "ieri 11" in blocco and "ieri 10\n" not in blocco
             and blocco.rstrip().endswith("ieri 40"), blocco)
    scrivi(v, "01-daily/%s.md" % GIOVEDI.isoformat(), "   \n")
    verifica("41b oggi vuoto: si usa ieri", "registro di ieri" in M.build_context())
    scrivi(v, "01-daily/%s.md" % GIOVEDI.isoformat(),
           "\n".join("riga %d" % i for i in range(1, 41)) + "\n")
    blocco = pezzi(M.build_context())[-1]
    righe = blocco.split("\n\n", 1)[1].splitlines()
    verifica("40 oggi 40 righe: solo le ultime 30",
             righe == ["riga %d" % i for i in range(11, 41)] and "registro di ieri" not in blocco, righe[:3])


def stato_posta(v, **campi):
    stato = {"ultimo_giro": "2030-01-10T07:05", "ultimo_ok": "2030-01-10T07:05",
             "esito": "ok", "errore": "", "resoconto": ".claude/data/mail-sync/2030-01-10.md",
             "mostrato": False, "visti": {"<id>": "2030-01-10"}, "riassunto": "àèì"}
    stato.update(campi)
    scrivi(v, ".claude/data/mail-sync/state.json", json.dumps(stato, indent=2))
    return stato


def leggi_stato(v):
    return json.loads((v / ".claude/data/mail-sync/state.json").read_text(encoding="utf-8"))


GIRO1 = "# Giro posta automatico, 2030-01-10 07:05\n\nPRIMO giro.\n\n## File toccati\n- `a.md`\n\n"
GIRO2 = "# Giro posta automatico, 2030-01-10 13:05\n\nSECONDO giro.\n\n## File toccati\n- `b.md`\n\n"


def test_posta():
    v = nuova_cartella("posta")
    scrivi(v, "CAPISALDI.md", "principi\n")
    scrivi(v, ".claude/data/mail-sync/2030-01-10.md", GIRO1 + GIRO2)

    # 22 (decisioni): guard non da' contesto; un altro valore non vuoto lo da' senza posta
    stato_posta(v)
    con_ambiente(v, "guard")
    verifica("22 guard: nessun contesto", M.build_context() == "")
    con_ambiente(v, "altro-script")
    ctx = M.build_context()
    verifica("22b altro invocatore: contesto senza posta",
             "## Capisaldi" in ctx and "Giro posta" not in ctx)
    verifica("22c mostrato resta falso", leggi_stato(v)["mostrato"] is False)

    # 43-44
    con_ambiente(v)
    prima = leggi_stato(v)
    ctx = M.build_context()
    posta = [p for p in pezzi(ctx) if "Giro posta" in p]
    verifica("43 un solo pezzo posta col secondo giro",
             len(posta) == 1 and "SECONDO" in posta[0] and "PRIMO" not in posta[0], ctx[:500])
    verifica("43b titolo del giro sceso al terzo livello",
             "\n### Giro posta automatico, 2030-01-10 13:05" in posta[0]
             and "\n# Giro" not in posta[0])
    verifica("43c dati non fidati dichiarati", "NON FIDATI" in posta[0])
    dopo = leggi_stato(v)
    verifica("43d mostrato vero, altri campi intatti",
             dopo["mostrato"] is True and {k: x for k, x in dopo.items() if k != "mostrato"}
             == {k: x for k, x in prima.items() if k != "mostrato"})
    testo_stato = (v / ".claude/data/mail-sync/state.json").read_text(encoding="utf-8")
    verifica("43e stato con rientro di 2 e accenti leggibili",
             '\n  "esito"' in testo_stato and "àèì" in testo_stato)
    verifica("43f nessun file temporaneo rimasto",
             [p.name for p in (v / ".claude/data/mail-sync").iterdir()
              if p.name.endswith(".tmp")] == [])
    verifica("44 seconda apertura: niente posta", "Giro posta" not in M.build_context())

    # 45-46 fallimento
    stato_posta(v, esito="errore", errore="Mail non risponde", ultimo_ok=None,
                ultimo_giro="2030-01-11T07:02:33")
    prima = (v / ".claude/data/mail-sync/state.json").read_text()
    ctx = M.build_context()
    verifica("45 avviso di fallimento",
             "Giro posta" in ctx and "Mail non risponde" in ctx and "2030-01-11 07:02" in ctx
             and "mai" in ctx and "loop_sync.py" in ctx, ctx[:800])
    verifica("45b stato non modificato",
             (v / ".claude/data/mail-sync/state.json").read_text() == prima)
    verifica("46 seconda apertura: avviso ancora presente", "Mail non risponde" in M.build_context())

    # 47
    scrivi(v, ".claude/data/mail-sync/state.json", "{non json")
    ctx = M.build_context()
    verifica("47 stato non JSON: niente posta, resto esce",
             "Giro posta" not in ctx and "## Capisaldi" in ctx)
    scrivi(v, ".claude/data/mail-sync/state.json", "[1, 2]")
    ctx = M.build_context()
    verifica("47b stato lista: niente posta, resto esce",
             "Giro posta" not in ctx and "## Capisaldi" in ctx)
    stato_posta(v, resoconto=42, mostrato="si")
    ctx = M.build_context()
    verifica("stato con tipi sbagliati: niente posta, resto esce",
             "Giro posta" not in ctx and "## Capisaldi" in ctx)

    # 48
    stato_posta(v, resoconto=".claude/data/mail-sync/manca.md")
    ctx = M.build_context()
    verifica("48 resoconto inesistente: niente pezzo, mostrato falso",
             "Giro posta" not in ctx and leggi_stato(v)["mostrato"] is False)

    # 49
    lungo = "# Giro posta automatico, 2030-01-12 07:00\n\n" + ("x" * 99 + "\n") * 50
    scrivi(v, ".claude/data/mail-sync/lungo.md", lungo)
    stato_posta(v, resoconto=".claude/data/mail-sync/lungo.md")
    posta = [p for p in pezzi(M.build_context()) if "Giro posta" in p][0]
    corpo = posta[posta.index("### Giro posta automatico"):]
    verifica("49 resoconto lungo tagliato a 3000 con rimando al file",
             corpo.count("x") <= 3000 and corpo.count("x") > 2900
             and corpo.rstrip().endswith("`.claude/data/mail-sync/lungo.md`)"), corpo[-200:])

    # resoconto senza titolo del giro: tutto il testo con il titolo davanti
    scrivi(v, ".claude/data/mail-sync/senza.md", "solo testo del giro\n")
    stato_posta(v, resoconto=".claude/data/mail-sync/senza.md")
    posta = [p for p in pezzi(M.build_context()) if "Giro posta" in p][0]
    verifica("resoconto senza titolo: titolo aggiunto",
             "### Giro posta automatico\n\nsolo testo del giro" in posta, posta)


def test_ordine_e_tetto():
    v = nuova_cartella("completo")
    con_ambiente(v)
    scrivi(v, "02-memoria/PROMOTE-QUEUE.md", CODA_UNO)
    scrivi(v, "CAPISALDI.md", "C\n")
    scrivi(v, "ARCHITETTURA.md", "A\n")
    scrivi(v, "02-memoria/me.md", "U\n")
    scrivi(v, "02-memoria/SOUL.md", "status: active\nS\n")
    scrivi(v, "01-daily/%s.md" % GIOVEDI.isoformat(), "appunto\n")
    scrivi(v, ".claude/data/mail-sync/2030-01-10.md", GIRO1)
    stato_posta(v)
    titoli = [p.splitlines()[0] for p in pezzi(M.build_context())]
    attesi = ["## Oggi", "## Giro posta", "## Memoria, coda promote", "## Capisaldi",
              "## Architettura", "## Chi e'", "## L'assistente", "## Appunti"]
    verifica("52 ordine dei pezzi",
             len(titoli) == len(attesi) and all(t.startswith(a) for t, a in zip(titoli, attesi)),
             titoli)
    verifica("51 sotto il tetto: nessun avviso", "contesto troncato" not in M.build_context())

    riga = "parola " * 14 + "\n"  # 99 caratteri
    scrivi(v, "ARCHITETTURA.md", riga * 700)  # circa 69.000 caratteri
    ctx = M.build_context()
    verifica("50 oltre il tetto: finisce con l'avviso",
             pezzi(ctx)[-1].startswith("## ATTENZIONE: contesto troncato"))
    prima = ctx[:ctx.rindex(M.SEPARATORE)]
    verifica("50b parte prima dell'avviso entro il tetto e a fine riga",
             len(prima) <= M.MAX_CONTEXT_CHARS and prima.endswith("parola"),
             (len(prima), prima[-30:]))
    verifica("50c la coda e' sparita (appunti assenti)", "appunto" not in ctx)
    avviso = pezzi(ctx)[-1]
    verifica("50d avviso senza diciture riservate e col tetto",
             all(d not in avviso for d in ("## Oggi", "coda promote", "Giro posta",
                                           "## Chi e'", "## Capisaldi"))
             and "58000" in avviso and "health_check.py" in avviso)
    verifica("nessun trattino lungo nel contesto", "\u2014" not in ctx)


def test_sorgente():
    import re
    testo = HOOK.read_text(encoding="utf-8")
    m = re.search(r"^MAX_CONTEXT_CHARS\s*=\s*([0-9_]+)\s*(#.*)?$", testo, re.MULTILINE)
    verifica("54 riga MAX_CONTEXT_CHARS leggibile come testo",
             m is not None and int(m.group(1).replace("_", "")) == 58000)
    verifica("nessun trattino lungo nel sorgente", "\u2014" not in testo)


def test_tempo_rete_lenta():
    """Caso peggiore: remoto ssh che non risponde mai, e remoto ssh lento ma vivo."""
    base = nuova_cartella("rete-lenta")
    nudo, vault, _ = remoto_e_cloni("rete-lenta-repo")
    fermo = base / "ssh-fermo.sh"
    fermo.write_text("#!/bin/sh\nsleep 60\n")
    fermo.chmod(0o755)
    lento = base / "ssh-lento.sh"
    # simula ssh: aspetta, poi esegue l'ultimo argomento (git-upload-pack '<percorso>')
    lento.write_text('#!/bin/sh\nsleep "${RITARDO:-4.8}"\nfor u; do :; done\nexec sh -c "$u"\n')
    lento.chmod(0o755)
    git(vault, "remote", "set-url", "origin", "ssh://finto.invalid" + str(nudo))
    scrivi(vault, "CAPISALDI.md", "principi\n")

    git(vault, "config", "ssh.variant", "ssh")  # niente sonda «-G»: una sola connessione
    git(vault, "config", "core.sshCommand", str(fermo))
    r, durata = esegui_hook(vault)
    ctx = json.loads(r.stdout.decode())["hookSpecificOutput"]["additionalContext"]
    verifica("tempo: remoto fermo, finisce entro 12 s (%.1f s)" % durata, durata < 12)
    verifica("tempo: remoto fermo, una riga dice che l'allineamento non e' fatto",
             "Allineamento col remoto non fatto" in ctx and "## Capisaldi" in ctx, ctx[:400])
    print("   durata con remoto fermo: %.2f s" % durata)

    git(vault, "config", "core.sshCommand", str(lento))
    os.environ["RITARDO"] = "4.5"
    try:
        r, durata = esegui_hook(vault)
    finally:
        os.environ.pop("RITARDO", None)
    ctx = json.loads(r.stdout.decode())["hookSpecificOutput"]["additionalContext"]
    verifica("tempo: remoto lento ma vivo, entro 12 s (%.1f s)" % durata, durata < 12)
    verifica("tempo: remoto lento, contesto uscito", "## Capisaldi" in ctx
             and "Allineamento col remoto non fatto" not in ctx
             and "Salvataggi cloud: controllo non fatto" in ctx)
    print("   remoto lento, primo pezzo: %r" % ctx.split(M.SEPARATORE)[0][:80])
    print("   durata con remoto lento (4.5 s a connessione): %.2f s" % durata)

    git(vault, "config", "core.sshCommand", str(lento))
    os.environ["RITARDO"] = "0"
    try:
        r, durata = esegui_hook(vault)
    finally:
        os.environ.pop("RITARDO", None)
    verifica("(controllo) il finto ssh funziona: in pari, nessun messaggio",
             r.returncode == 0 and b"Allineamento" not in r.stdout and b"Oggi" in r.stdout,
             r.stdout[:300])


def main():
    prove = [test_git, test_git_mai_eseguito, test_contesto_base, test_coda,
             test_documenti_e_appunti, test_posta, test_ordine_e_tetto, test_sorgente,
             test_tempo_rete_lenta]
    try:
        for prova in prove:
            try:
                prova()
            except Exception as e:
                import traceback
                traceback.print_exc()
                verifica("%s senza eccezioni" % prova.__name__, False, repr(e))
    finally:
        shutil.rmtree(RADICE_PROVE, ignore_errors=True)
    passati = sum(1 for _, ok in ESITI if ok)
    print("%d/%d test passati" % (passati, len(ESITI)))
    return 0 if passati == len(ESITI) else 1


if __name__ == "__main__":
    sys.exit(main())
