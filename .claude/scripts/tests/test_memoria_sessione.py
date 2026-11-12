# 2nd Brain Hero Mode · Copyright (c) 2026 Alessandro Pacifico (Pacibrand).
# Vedi LICENZA.md nella radice del vault.
"""Prove di `shared.py`, dei due hook di salvataggio e di `memory_flush.py`.

Script autonomo, senza pytest: `python3 test_memoria_sessione.py`. Ogni prova lavora in
un vault temporaneo con CLAUDE_PROJECT_DIR puntata li'. Il modello e' sempre finto
(MEMORY_FLUSH_STUB, MEMORY_FLUSH_JUDGE_STUB, oppure un finto `claude` scritto dalla
prova): `claude` vero non viene mai lanciato. L'ultima riga stampata e' `N/M test
passati`; il codice di uscita e' 1 se qualcosa fallisce.

I numeri nei nomi delle prove rimandano ai casi delle specifiche: S = shared.md,
H = flush-hooks.md, M = memory_flush.md, D = decisioni.md (dove vince su una specifica).
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path

QUI = Path(__file__).resolve().parent
SCRIPTS = QUI.parent
HOOKS = SCRIPTS.parent / "hooks"
sys.path.insert(0, str(SCRIPTS))

import shared  # noqa: E402
import memory_flush as mf  # noqa: E402

PY = sys.executable
INTESTAZIONE = "# 2nd Brain Hero Mode · Copyright (c) 2026 Alessandro Pacifico (Pacibrand)."
TRATTINO_LUNGO = chr(0x2014)

# ---------------------------------------------------------------------------
# Materiale di prova
# ---------------------------------------------------------------------------

CODA_KIT = """# PROMOTE-QUEUE: candidati alla memoria

Qui l'agente propone cosa ricordare; l'utente o lo smaltimento decidono.

---

## In attesa

<!--
L'agente AGGIUNGE qui i candidati con questo formato:
### [AAAA-MM-GG] tipo → destinazione
**Proposta:** testo
**Fonte:** sessione chat AAAA-MM-GG
**Stato:** da rivedere
-->

_Nessun candidato in coda._

---

## Promossi (storico)

_Vuoto._
"""

MEMORY_LISTINO = "# Dossier\n\n## Decisioni\n\nListino mensile confermato: tre fasce da 390, 590 e 990 euro.\n"


def cand_listino(dest="MEMORY.md di progetto", extra=""):
    return ("### [2030-01-10] decisione → {}\n"
            "**Proposta:** Listino mensile confermato dall'utente: tre fasce da 390, 590 e 990 euro.{}\n"
            "**Fonte:** sessione chat 2030-01-10\n"
            "**Stato:** da rivedere").format(dest, extra)


CAND_CARTO = ("### [2030-01-10] fatto → MEMORY.md di progetto\n"
              "**Proposta:** Il fornitore Cartotecnica Alfa consegna le scatole personalizzate in ventuno giorni lavorativi.\n"
              "**Fonte:** sessione chat 2030-01-10\n"
              "**Stato:** da rivedere")


def risposta(riassunto="- Fissato il listino a tre fasce\n- Scelto il fornitore", candidati="NONE"):
    return "===DAILY===\n{}\n===CANDIDATES===\n{}\n".format(riassunto, candidati)


SI_C1 = '[{"id": "C1", "gia_scritto": true, "passaggio": 1}]'

TESTO_LUNGO = ("Fissiamo il listino a tre fasce mensili e scegliamo il fornitore delle scatole, "
               "poi verifichiamo i tempi di consegna con calma prima di chiudere la giornata. ")

# ---------------------------------------------------------------------------
# Strumenti
# ---------------------------------------------------------------------------

BASE = Path(tempfile.mkdtemp(prefix="stanza-memoria-"))
PROVE = []
VIOLAZIONI = []


def prova(nome):
    def registra(f):
        PROVE.append((nome, f))
        return f
    return registra


def check(cond, messaggio="condizione falsa"):
    if not cond:
        raise AssertionError(messaggio)


def cartella():
    return Path(tempfile.mkdtemp(dir=str(BASE)))


def nuovo_vault(coda=CODA_KIT, con_script=False):
    v = cartella()
    (v / "01-daily").mkdir()
    (v / "02-memoria").mkdir()
    if coda is not None:
        (v / "02-memoria" / "PROMOTE-QUEUE.md").write_text(coda, encoding="utf-8")
    if con_script:
        dest = v / ".claude" / "scripts"
        dest.mkdir(parents=True)
        shutil.copy(str(SCRIPTS / "shared.py"), str(dest / "shared.py"))
        shutil.copy(str(SCRIPTS / "memory_flush.py"), str(dest / "memory_flush.py"))
    os.environ["CLAUDE_PROJECT_DIR"] = str(v)
    return v


def scrivi(path, testo):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(testo, encoding="utf-8")
    return path


def turno(ruolo, contenuto):
    return {"type": ruolo, "message": {"role": ruolo, "content": contenuto}}


def uso(nome, ingresso):
    return {"type": "tool_use", "name": nome, "input": ingresso}


def trascrizione(righe, path=None):
    path = Path(path) if path else cartella() / "t.jsonl"
    testo = "\n".join(r if isinstance(r, str) else json.dumps(r, ensure_ascii=False) for r in righe)
    path.write_text(testo + "\n", encoding="utf-8")
    return str(path)


def trascrizione_lunga():
    return trascrizione([
        turno("user", TESTO_LUNGO),
        turno("assistant", [{"type": "text", "text": TESTO_LUNGO},
                            uso("Write", {"file_path": "/fuori/x.md", "content": "y"})]),
        turno("user", TESTO_LUNGO),
    ])


def oggi():
    return time.strftime("%Y-%m-%d")


def appunti(v):
    return v / "01-daily" / "{}.md".format(oggi())


def coda(v):
    return shared.read_text(v / "02-memoria" / "PROMOTE-QUEUE.md")


def registro(v):
    return shared.read_text(v / ".claude" / "data" / "flush" / "flush.log")


def attendi(cond, secondi=8.0):
    fine = time.time() + secondi
    while time.time() < fine:
        if cond():
            return True
        time.sleep(0.1)
    return cond()


def ambiente_figlio(**extra):
    """Copia dell'ambiente per un processo figlio, con le aggiunte indicate."""
    copia = os.environ.copy()
    copia.update(extra)
    return copia


def lancia(args, ingresso="", env=None, cwd=None):
    return subprocess.run(args, input=ingresso.encode("utf-8"), capture_output=True,
                          env=env if env is not None else ambiente_figlio(), cwd=cwd, timeout=60)


def py_shared(codice):
    """Comando che esegue `codice` con `shared` importabile."""
    return [PY, "-c", "import sys; sys.path.insert(0, {!r}); import shared\n{}".format(str(SCRIPTS), codice)]


def cattura_giudice(risposta_fissa):
    chiamate = []

    def finto(richiesta):
        chiamate.append(richiesta)
        return risposta_fissa
    mf._risposta_giudice = finto
    return chiamate


def finto_claude(cartella_bin, file_annotazioni):
    """Un eseguibile `claude` finto: annota argomenti e freno, risponde in formato."""
    cartella_bin.mkdir(parents=True, exist_ok=True)
    exe = cartella_bin / "claude"
    righe = [
        "#!" + PY,
        "import json, os, sys",
        "freno = os.getenv('CLAUDE_INVOKED_BY')",
        "nota = {'argv': sys.argv[1:], 'invoked': freno}",
        "with open(%r, 'a') as f:" % str(file_annotazioni),
        "    f.write(json.dumps(nota) + '\\n')",
        "if '--setting-sources' in sys.argv:",
        "    print('[]')",
        "else:",
        "    print(%r)" % risposta(candidati=CAND_CARTO),
    ]
    exe.write_text("\n".join(righe) + "\n", encoding="utf-8")
    exe.chmod(0o755)
    return exe


# ===========================================================================
# shared.py
# ===========================================================================

@prova("S5 vault_root legge CLAUDE_PROJECT_DIR")
def _():
    os.environ["CLAUDE_PROJECT_DIR"] = "/tmp/v"
    check(shared.vault_root() == Path("/tmp/v"))
    check(isinstance(shared.vault_root(), Path))


@prova("S6 vault_root senza variabile usa la cartella corrente")
def _():
    os.environ.pop("CLAUDE_PROJECT_DIR", None)
    w = cartella()
    os.chdir(str(w))
    check(shared.vault_root().resolve() == w.resolve())


@prova("S7 la variabile si rilegge a ogni chiamata")
def _():
    os.environ["CLAUDE_PROJECT_DIR"] = "/tmp/uno"
    shared.vault_root()
    os.environ["CLAUDE_PROJECT_DIR"] = "/tmp/due"
    check(shared.vault_root() == Path("/tmp/due"))


@prova("S8-S11 read_text: accenti, assente, cartella, byte non UTF-8")
def _():
    v = nuovo_vault()
    f = scrivi(v / "a.md", "perché così è")
    check(shared.read_text(f) == "perché così è")
    check(shared.read_text(v / "manca.md") == "")
    check(shared.read_text(v) == "")
    (v / "rotto.md").write_bytes(b"abc\xff\xfe")
    check(shared.read_text(v / "rotto.md") == "")


@prova("S12-S14 append_text: crea cartelle, nessun a capo aggiunto")
def _():
    v = nuovo_vault()
    f = v / "nuova" / "cartella" / "f.md"
    shared.append_text(f, "a\n")
    check(f.read_text(encoding="utf-8") == "a\n")
    shared.append_text(f, "b\n")
    check(f.read_text(encoding="utf-8") == "a\nb\n")
    g = v / "g.md"
    shared.append_text(g, "senza a capo")
    check(g.read_text(encoding="utf-8") == "senza a capo")


@prova("S15 venti processi per cento aggiunte: duemila righe intere")
def _():
    v = nuovo_vault()
    f = v / "concorrenza.md"
    codice = "for i in range(100): shared.append_text({!r}, 'proc-%s-riga-%03d-' % (sys.argv[1], i) + 'x' * 200 + '\\n')".format(str(f))
    procs = [subprocess.Popen(py_shared(codice) + [str(n).zfill(2)]) for n in range(20)]
    for p in procs:
        check(p.wait(timeout=120) == 0, "processo fallito")
    righe = f.read_text(encoding="utf-8").split("\n")
    check(righe[-1] == "")
    righe = righe[:-1]
    check(len(righe) == 2000, "righe: {}".format(len(righe)))
    check(all(r.startswith("proc-") and r.endswith("x" * 200) and len(r) == len(righe[0]) for r in righe))


@prova("S16-S17 write_text_atomic: sostituisce, crea cartelle, nessun temporaneo rimasto")
def _():
    v = nuovo_vault()
    f = scrivi(v / "state.json", "vecchio contenuto lungo")
    shared.write_text_atomic(f, "nuovo")
    check(f.read_text(encoding="utf-8") == "nuovo")
    check([p.name for p in v.iterdir() if p.name.endswith(".tmp")] == [])
    g = v / "non" / "esiste" / "s.json"
    shared.write_text_atomic(g, "x")
    check(g.read_text(encoding="utf-8") == "x")


@prova("S18 un lettore vede sempre una versione intera")
def _():
    v = nuovo_vault()
    f = scrivi(v / "s.txt", "A" * 20000)
    codice = "for i in range(300): shared.write_text_atomic({!r}, ('B' if i % 2 else 'A') * 20000)".format(str(f))
    p = subprocess.Popen(py_shared(codice))
    letture = 0
    while p.poll() is None:
        t = f.read_text(encoding="utf-8")
        check(t in ("A" * 20000, "B" * 20000), "versione mista o vuota ({} char)".format(len(t)))
        letture += 1
    check(p.returncode == 0)
    check(letture > 0)


@prova("S19-S20 file di blocco lontani dal bersaglio, uno per percorso")
def _():
    v = nuovo_vault()
    shared.append_text(v / "02-memoria" / "x.md", "riga\n")
    check(not [p for p in (v / "02-memoria").iterdir() if p.name.endswith(".lock")])
    blocchi = [p.name for p in (v / ".claude" / "data" / "locks").iterdir()]
    check(any(n.startswith("x.md.") and n.endswith(".lock") for n in blocchi))
    shared.append_text(v / "a" / "nota.md", "1")
    shared.append_text(v / "b" / "nota.md", "2")
    note = [n.name for n in (v / ".claude" / "data" / "locks").iterdir() if n.name.startswith("nota.md.")]
    check(len(note) == 2, str(note))


def _tieni_blocco(f, secondi):
    codice = "import time\nwith shared.file_lock({!r}):\n    print('preso', flush=True)\n    time.sleep({})".format(str(f), secondi)
    p = subprocess.Popen(py_shared(codice), stdout=subprocess.PIPE)
    check(p.stdout.readline().strip() == b"preso")
    return p


@prova("S21 blocco occupato: tempo scaduto dopo circa mezzo secondo, file intatto")
def _():
    v = nuovo_vault()
    f = scrivi(v / "c.md", "prima\n")
    p = _tieni_blocco(f, 3)
    t0 = time.time()
    try:
        shared.append_text(f, "dopo\n", timeout=0.5)
        check(False, "nessun errore")
    except TimeoutError:
        pass
    durata = time.time() - t0
    check(0.4 <= durata <= 1.5, "durata {}".format(durata))
    check(f.read_text(encoding="utf-8") == "prima\n")
    try:
        shared.write_text_atomic(f, "x", timeout=0.3)
        check(False, "nessun errore")
    except TimeoutError:
        pass
    check(f.read_text(encoding="utf-8") == "prima\n")
    p.wait()


@prova("S22 blocco rilasciato entro il tempo: la scrittura riesce")
def _():
    v = nuovo_vault()
    f = v / "c.md"
    p = _tieni_blocco(f, 0.5)
    shared.append_text(f, "ok\n", timeout=5)
    check(f.read_text(encoding="utf-8") == "ok\n")
    p.wait()


@prova("S23 processo morto col blocco: il blocco si libera")
def _():
    v = nuovo_vault()
    f = v / "c.md"
    p = _tieni_blocco(f, 60)
    p.kill()
    p.wait()
    t0 = time.time()
    shared.append_text(f, "ok\n", timeout=2)
    check(time.time() - t0 < 1.0)


@prova("S24-S28 + D invoked_by_flush: flush, mail-sync, guard veri; altro falso")
def _():
    for valore, atteso in (("flush", True), ("mail-sync", True), ("guard", True),
                           ("", False), ("altro", False)):
        os.environ["CLAUDE_INVOKED_BY"] = valore
        check(shared.invoked_by_flush() is atteso, valore)
    os.environ.pop("CLAUDE_INVOKED_BY", None)
    check(shared.invoked_by_flush() is False)


@prova("S29 launch_flush senza programma: falso, niente creato")
def _():
    v = nuovo_vault()
    check(shared.launch_flush(trigger="session_end", transcript_path="", session_id="") is False)
    check(not (v / ".claude").exists())


def _vault_con_finto_programma(corpo):
    v = nuovo_vault()
    scrivi(v / ".claude" / "scripts" / "memory_flush.py", corpo)
    return v


FINTO_PROGRAMMA = """import json, os, sys, time
time.sleep(float(os.getenv('FINTO_ATTESA', '0')))
freno = os.getenv('CLAUDE_INVOKED_BY')
visto = {'argv': sys.argv[1:], 'invoked': freno, 'cwd': os.getcwd()}
with open(os.path.join(os.getcwd(), 'visto.json'), 'w') as f:
    json.dump(visto, f)
print('stampato dal programma')
raise RuntimeError('errore voluto')
"""


@prova("S30-S33, S35 launch_flush: parte subito, opzioni, ambiente, cartella, registro")
def _():
    v = _vault_con_finto_programma(FINTO_PROGRAMMA)
    scrivi(v / ".claude" / "data" / "flush" / "flush.log", "riga gia' presente\n")
    t0 = time.time()
    check(shared.launch_flush(trigger="pre_compact", transcript_path="/t.jsonl", session_id="abc") is True)
    check(time.time() - t0 < 1.0)
    check("CLAUDE_INVOKED_BY" not in os.environ)
    check(attendi(lambda: (v / "visto.json").exists() and "errore voluto" in registro(v)))
    visto = json.loads((v / "visto.json").read_text())
    check(visto["argv"] == ["--trigger", "pre_compact", "--transcript", "/t.jsonl", "--session-id", "abc"], str(visto))
    check(visto["invoked"] == "flush")
    check(Path(visto["cwd"]).resolve() == v.resolve())
    log = registro(v)
    check(log.startswith("riga gia' presente\n") and "stampato dal programma" in log)


@prova("S32 launch_flush con valori nulli: opzioni vuote")
def _():
    v = _vault_con_finto_programma(FINTO_PROGRAMMA)
    shared.launch_flush(trigger=None, transcript_path=None, session_id=None)
    check(attendi(lambda: (v / "visto.json").exists()))
    visto = json.loads((v / "visto.json").read_text())
    check(visto["argv"] == ["--trigger", "", "--transcript", "", "--session-id", ""])


@prova("S34 il chiamante esce subito, il programma lanciato continua")
def _():
    v = _vault_con_finto_programma(FINTO_PROGRAMMA)
    r = lancia(py_shared("shared.launch_flush(trigger='x', transcript_path='', session_id='')"),
               env=ambiente_figlio(FINTO_ATTESA="1.5"))
    check(r.returncode == 0)
    check(not (v / "visto.json").exists())
    check(attendi(lambda: (v / "visto.json").exists()))


@prova("S36 importare shared e memory_flush non crea nulla e non stampa")
def _():
    v = cartella()
    r = lancia([PY, "-c", "import sys; sys.path.insert(0, {!r}); import shared, memory_flush".format(str(SCRIPTS))],
               env=ambiente_figlio(CLAUDE_PROJECT_DIR=str(v)), cwd=str(v))
    check(r.returncode == 0 and r.stdout == b"" and r.stderr == b"", r.stderr.decode())
    check(list(v.iterdir()) == [])


@prova("D temporaneo nascosto `.nome.tmp`: interruzione lascia il bersaglio intatto")
def _():
    v = nuovo_vault()
    f = scrivi(v / "state.json", "vecchio")
    originale = os.replace

    def rotto(a, b):
        raise OSError("interrotto")
    os.replace = rotto
    try:
        shared.write_text_atomic(f, "nuovo")
        check(False, "nessun errore")
    except OSError:
        pass
    finally:
        os.replace = originale
    check(f.read_text() == "vecchio")
    check((v / ".state.json.tmp").exists())
    shared.write_text_atomic(f, "nuovo")
    check(f.read_text() == "nuovo" and not (v / ".state.json.tmp").exists())


@prova("D update_text: dieci aggiornamenti paralleli della coda, nessuna voce persa")
def _():
    v = nuovo_vault()
    q = v / "02-memoria" / "PROMOTE-QUEUE.md"
    codice = ("sys.path.insert(0, {s!r}); import memory_flush as mf\n"
              "n = sys.argv[1]\n"
              "blocco = '### [2030-01-10] fatto → wiki globale\\n**Proposta:** voce parallela %s\\n**Fonte:** x\\n**Stato:** da rivedere' % n\n"
              "shared.update_text({q!r}, lambda t: mf.insert_candidates(t, blocco))").format(s=str(SCRIPTS), q=str(q))
    procs = [subprocess.Popen(py_shared(codice) + [str(n)]) for n in range(10)]
    for p in procs:
        check(p.wait(timeout=60) == 0)
    testo = coda(v)
    check(all("voce parallela {}\n".format(n) in testo for n in range(10)))
    check(mf.SEGNAPOSTO_CODA not in testo and "## Promossi (storico)" in testo)


# ===========================================================================
# Hook
# ===========================================================================

def hook(nome, ingresso, env_extra=None, togli=()):
    env = ambiente_figlio(**(env_extra or {}))
    for k in togli:
        env.pop(k, None)
    return lancia([PY, str(HOOKS / nome)], ingresso=ingresso, env=env)


@prova("H1 H3 H6 + D hook con CLAUDE_INVOKED_BY di servizio: uscita 0, nessun lancio")
def _():
    t = trascrizione_lunga()
    for nome in ("session-end-flush.py", "pre-compact-flush.py"):
        for valore in ("flush", "mail-sync", "guard"):
            v = nuovo_vault(con_script=True)
            r = hook(nome, json.dumps({"transcript_path": t, "session_id": "s"}),
                     {"CLAUDE_INVOKED_BY": valore, "MEMORY_FLUSH_STUB": risposta()})
            check(r.returncode == 0 and r.stdout == b"" and r.stderr == b"")
            time.sleep(0.3)
            check(not (v / ".claude" / "data").exists(), "lanciato con " + valore)
            check(not appunti(v).exists())


@prova("H2 H4 H5 H7 hook reali: l'appunto compare, intestazione con l'innesco giusto")
def _():
    t = trascrizione_lunga()
    for nome, etichetta, extra in (("session-end-flush.py", "session_end", {}),
                                   ("pre-compact-flush.py", "pre_compact", {}),
                                   ("session-end-flush.py", "session_end", {"CLAUDE_INVOKED_BY": "altro"})):
        v = nuovo_vault(con_script=True)
        env = {"MEMORY_FLUSH_STUB": risposta(riassunto="- Riassunto finto dell'hook")}
        env.update(extra)
        t0 = time.time()
        r = hook(nome, json.dumps({"transcript_path": t, "session_id": "abcdefghijk", "altro": 1}), env,
                 togli=() if extra else ("CLAUDE_INVOKED_BY",))
        check(time.time() - t0 < 3.0, "hook lento")
        check(r.returncode == 0 and r.stdout == b"" and r.stderr == b"", r.stderr.decode())
        check(attendi(lambda: "Riassunto finto dell'hook" in shared.read_text(appunti(v))), "appunto assente")
        check("## Flush sessione, " in shared.read_text(appunti(v)))
        check("· {}".format(etichetta) in shared.read_text(appunti(v)))
        check(attendi(lambda: "session=abcdefgh\n" in registro(v)))


@prova("H8 H9 H11 ingresso vuoto, non JSON, solo session_id: lancio, riga troppo breve")
def _():
    for ingresso in ("", "non sono json", json.dumps({"session_id": "solo"})):
        v = nuovo_vault(con_script=True)
        r = hook("session-end-flush.py", ingresso, {"MEMORY_FLUSH_STUB": risposta()}, togli=("CLAUDE_INVOKED_BY",))
        check(r.returncode == 0 and r.stdout == b"" and r.stderr == b"")
        check(attendi(lambda: "troppo breve (0 char)" in registro(v)), "registro: " + registro(v))
        check(not appunti(v).exists())


@prova("H10 ingresso JSON che non e' un oggetto: nessun lancio")
def _():
    v = nuovo_vault(con_script=True)
    r = hook("pre-compact-flush.py", "[1, 2]", {"MEMORY_FLUSH_STUB": risposta()}, togli=("CLAUDE_INVOKED_BY",))
    check(r.returncode == 0 and r.stdout == b"" and r.stderr == b"")
    time.sleep(0.3)
    check(not (v / ".claude" / "data").exists())


@prova("H12 H13 vault senza memory_flush.py: uscita 0, silenzio")
def _():
    v = nuovo_vault()
    for nome in ("session-end-flush.py", "pre-compact-flush.py"):
        r = hook(nome, json.dumps({"transcript_path": "x"}), togli=("CLAUDE_INVOKED_BY",))
        check(r.returncode == 0 and r.stdout == b"" and r.stderr == b"")
    check(not (v / ".claude").exists())


@prova("H14 il tempo dell'hook non dipende dal salvataggio")
def _():
    v = _vault_con_finto_programma(FINTO_PROGRAMMA)
    t0 = time.time()
    r = hook("session-end-flush.py", "{}", {"FINTO_ATTESA": "4"}, togli=("CLAUDE_INVOKED_BY",))
    check(r.returncode == 0 and time.time() - t0 < 2.0)
    check(not (v / "visto.json").exists())


@prova("D hook senza libreria accanto: uscita 0, silenzio")
def _():
    d = cartella()
    (d / "hooks").mkdir()
    for nome in ("session-end-flush.py", "pre-compact-flush.py"):
        shutil.copy(str(HOOKS / nome), str(d / "hooks" / nome))
        r = lancia([PY, str(d / "hooks" / nome)], ingresso="{}")
        check(r.returncode == 0 and r.stdout == b"" and r.stderr == b"")


# ===========================================================================
# memory_flush.py: lettura della risposta
# ===========================================================================

@prova("M1 M2 M3 parse_output: marcatori, NONE, senza marcatori")
def _():
    r, c = mf.parse_output(risposta("- primo punto\n- secondo punto", cand_listino()))
    check("primo punto" in r and "secondo punto" in r)
    check("### [2030-01-10]" in c)
    check(mf.parse_output(risposta(candidati="NONE"))[1] == "")
    check(mf.parse_output("testo senza marcatori") == ("testo senza marcatori", ""))


@prova("M21-M25 parse_output: preambolo, un solo marcatore, none, riassunto vuoto, vuoto")
def _():
    r, _c = mf.parse_output("Ecco a te:\n===DAILY===\n- punto\n===CANDIDATES===\nNONE")
    check("Ecco" not in r and r == "- punto")
    check(mf.parse_output("===DAILY===\n- solo riassunto\n") == ("- solo riassunto", ""))
    check(mf.parse_output("===DAILY===\n- x\n===CANDIDATES===\nnone\n")[1] == "")
    r, c = mf.parse_output("===DAILY===\n\n===CANDIDATES===\n" + CAND_CARTO)
    check(r == "" and c == CAND_CARTO)
    check(mf.parse_output("") == ("", ""))


# ===========================================================================
# memory_flush.py: trascrizione
# ===========================================================================

@prova("M4 extract_conversation: ruoli, niente tool_use")
def _():
    t = trascrizione([
        turno("user", "Fissiamo il listino a tre fasce."),
        turno("assistant", [{"type": "text", "text": "Lo scrivo nel dossier."},
                            uso("Write", {"file_path": "/v/MEMORY.md", "content": "Listino"})]),
        turno("user", [{"type": "tool_result", "content": "ok"}]),
        turno("user", "Perfetto."),
    ])
    c = mf.extract_conversation(t)
    check("tool_use" not in c and "tool_result" not in c)
    check(c == "[user] Fissiamo il listino a tre fasce.\n\n[assistant] Lo scrivo nel dossier.\n\n[user] Perfetto.", repr(c))


@prova("M26-M29 + D extract_conversation: assente, righe rotte, solo risultati, altri ruoli, JSON non oggetto")
def _():
    check(mf.extract_conversation("") == "")
    check(mf.extract_conversation(str(cartella() / "manca.jsonl")) == "")
    t = trascrizione([
        turno("user", "uno"),
        "questa riga non e' json {",
        "[1, 2, 3]",
        "\"stringa\"",
        "",
        turno("user", [{"type": "tool_result", "content": "solo risultato"}]),
        turno("system", "sistema"),
        {"type": "x", "message": "non oggetto"},
        turno("assistant", "due"),
    ])
    check(mf.extract_conversation(t) == "[user] uno\n\n[assistant] due")


@prova("M30 conversazione di 60.000 caratteri: restano gli ultimi 40.000")
def _():
    t = trascrizione([turno("user", "a" * 30000), turno("assistant", "b" * 30000)])
    c = mf.extract_conversation(t)
    check(len(c) == 40000 and c.endswith("b" * 30000))


# ===========================================================================
# memory_flush.py: scritture della sessione
# ===========================================================================

def _scritture(blocchi):
    return trascrizione([turno("assistant", blocchi)])


@prova("M11 extract_written: MEMORY.md di progetto si', appunto e Bash no")
def _():
    v = nuovo_vault()
    t = _scritture([
        uso("Write", {"file_path": str(v / "10-lavoro/progetto/MEMORY.md"),
                      "content": "Listino fissato: tre fasce mensili da 390, 590 e 990 euro."}),
        uso("Edit", {"file_path": str(v / "01-daily/2030-01-10.md"), "old_string": "x",
                     "new_string": "Oggi giornata lunga, tanto caffe' al bar e poche chiamate utili."}),
        uso("Bash", {"command": "echo 'Listino da 1234 euro scritto con bash' > 10-lavoro/progetto/MEMORY.md"}),
    ])
    e = mf.extract_written(t, v)
    check("10-lavoro/progetto/MEMORY.md" in e and "390, 590 e 990" in e, e)
    check("caffe" not in e and "1234" not in e)
    check(e.startswith("- 10-lavoro/progetto/MEMORY.md: «") and e.endswith("»"))


@prova("M31-M33 extract_written: fuori vault, knowledge/raw, testo corto")
def _():
    v = nuovo_vault()
    lungo = "Un testo abbastanza lungo da superare la soglia dei quaranta caratteri utili."
    t = _scritture([
        uso("Write", {"file_path": "/altrove/10-lavoro/p/MEMORY.md", "content": lungo}),
        uso("Write", {"file_path": str(v / "10-lavoro/p/knowledge/raw/fonte.md"), "content": lungo}),
        uso("Edit", {"file_path": str(v / "10-lavoro/p/MEMORY.md"), "new_string": "dieci car."}),
    ])
    check(mf.extract_written(t, v) == "")


@prova("M34-M37 extract_written: ultime quattro, MultiEdit, una riga da 700, vuoto")
def _():
    v = nuovo_vault()
    pad = " con abbastanza testo per superare la soglia minima di quaranta caratteri"
    nomi = ["primo", "secondo", "terzo", "quarto", "quinto", "sesto"]
    blocchi = [uso("Edit", {"file_path": str(v / "10-lavoro/p/MEMORY.md"), "new_string": n + pad}) for n in nomi]
    blocchi.append(uso("MultiEdit", {"file_path": "10-lavoro/p/README.md", "edits": [
        {"new_string": "modifica uno" + pad}, {"new_string": "modifica due" + pad}]}))
    blocchi.append(uso("Write", {"file_path": str(v / "02-memoria/wiki/pagina.md"),
                                 "content": ("riga di testo\n\n  altra   riga " * 200)[:2000]}))
    e = mf.extract_written(_scritture(blocchi), v)
    righe = e.split("\n")
    memoria = [r for r in righe if r.startswith("- 10-lavoro/p/MEMORY.md: ")]
    check([r.split("«")[1].split(" ")[0] for r in memoria] == ["terzo", "quarto", "quinto", "sesto"], str(memoria))
    check(len([r for r in righe if r.startswith("- 10-lavoro/p/README.md: ")]) == 2)
    wiki = [r for r in righe if r.startswith("- 02-memoria/wiki/pagina.md: ")]
    check(len(wiki) == 1)
    estratto = wiki[0][len("- 02-memoria/wiki/pagina.md: «"):-1]
    check(len(estratto) == 700 and "\n" not in estratto and "  " not in estratto)
    check(righe.index(memoria[0]) < righe.index(wiki[0]))
    check(mf.extract_written(_scritture([uso("Bash", {"command": "ls"})]), v) == "")
    check(mf.extract_written("", v) == "")


@prova("M punto 3 extract_written: elenco fermo sotto i 9.000 caratteri")
def _():
    v = nuovo_vault()
    blocchi = [uso("Write", {"file_path": str(v / "10-lavoro/p{}/MEMORY.md".format(i)), "content": "z" * 800})
               for i in range(20)]
    e = mf.extract_written(_scritture(blocchi), v)
    check(8000 < len(e) <= 9000, str(len(e)))


# ===========================================================================
# memory_flush.py: richiesta e file di memoria
# ===========================================================================

@prova("M12 build_prompt con e senza elenco delle scritture")
def _():
    con = mf.build_prompt("[user] conversazione", "2030-01-10", "- 10-lavoro/p/MEMORY.md: «x»")
    senza = mf.build_prompt("[user] conversazione", "2030-01-10")
    check("GIA' scritte su disco" in con and "- 10-lavoro/p/MEMORY.md: «x»" in con)
    check("GIA' scritte su disco" not in senza)
    for p in (con, senza):
        check("===DAILY===" in p and "===CANDIDATES===" in p and "NONE" in p)
        check("[2030-01-10]" in p and p.rstrip().endswith("<<<FINE TRASCRIZIONE>>>"))
        check("[user] conversazione" in p and TRATTINO_LUNGO not in p)
        check("references/metodo.md di <nome del progetto>" in p)


@prova("M17 M38 M39 + D is_memory_file secondo decisioni.md")
def _():
    falsi = ["01-daily/2030-01-10.md", "10-lavoro/x/knowledge/calls/c.md", "02-memoria/PROMOTE-QUEUE.md",
             "README.md", "10-lavoro/p/CLAUDE.md", "02-memoria/wiki/raw/CAPISALDI.md",
             "x/ARCHITETTURA.md", "claude.md", "audit-log.md", "02-memoria/PROMOTE-ARCHIVIO.md", "00-inbox/nota.md",
             ".claude/data/x.md", ".claude/tmp/x.md", ".obsidian/x.md", "02-memoria/wiki/raw/x.md",
             "nota.txt", "raw.md", "10-lavoro/p/references/calls.md", "10-lavoro/README.md",
             "_local-only/02-memoria/x.md", ".claude/skills/x/README.md", "10-lavoro/p/note.md",
             "10-lavoro/p/references/brand.md", "metodo.md", "references/metodo.md"]
    veri = ["10-lavoro/x/knowledge/wiki/pagina.md", "02-memoria/me.md", "02-memoria/wiki/pagina.md",
            "10-lavoro/p/MEMORY.md", "10-lavoro/p/README.md", "30-personale/casa/MEMORY.md",
            "02-memoria/wiki/me-regole.md", "CLAUDE.md", "CAPISALDI.md", "ARCHITETTURA.md",
            "10-lavoro/p/references/metodo.md", "20-fiscale-legale/references/metodo.md"]
    for f in falsi:
        check(mf.is_memory_file(f) is False, f)
    for f in veri:
        check(mf.is_memory_file(f) is True, f)


# ===========================================================================
# memory_flush.py: controllo dei doppioni
# ===========================================================================

def vault_listino(dove="10-lavoro/progetto/MEMORY.md", coda_testo=CODA_KIT):
    v = nuovo_vault(coda=coda_testo)
    scrivi(v / dove, MEMORY_LISTINO)
    scrivi(v / "01-daily" / "2030-01-09.md", "# Daily\n\nListino mensile 390, 590 e 990 euro confermato.\n")
    return v


@prova("M13 doppione in MEMORY.md di progetto: fermato con la fonte esatta")
def _():
    v = vault_listino()
    os.environ["MEMORY_FLUSH_JUDGE_STUB"] = SI_C1
    blocco, fermati = mf.filter_duplicates(v, cand_listino())
    check(blocco == "" and len(fermati) == 1, str(fermati))
    check(fermati[0][1] == "10-lavoro/progetto/MEMORY.md")
    check(fermati[0][0].startswith("decisione → MEMORY.md di progetto Listino mensile") and len(fermati[0][0]) <= 130)


@prova("M14 destinato a 02-memoria/me.md, trovato nel progetto: resta (regola del livello)")
def _():
    v = vault_listino()
    os.environ["MEMORY_FLUSH_JUDGE_STUB"] = SI_C1
    blocco, fermati = mf.filter_duplicates(v, cand_listino("02-memoria/me.md"))
    check("02-memoria/me.md" in blocco and fermati == [])


@prova("M15 M16 M46 M47 M48 giudice malformato o senza prova: resta; testo attorno: letto")
def _():
    v = vault_listino()
    for risposta_giudice in ("non sono un json",
                             '[{"id": "C1", "gia_scritto": true, "passaggio": 0}]',
                             '[{"id": "C1", "gia_scritto": true, "passaggio": 9}]',
                             '[{"id": "C1", "gia_scritto": "true", "passaggio": 1}]',
                             '[{"id": "C1", "gia_scritto": true, "passaggio": true}]',
                             '[{"id": "C7", "gia_scritto": true, "passaggio": 1}, 5, "x"]',
                             '{"id": "C1", "gia_scritto": true, "passaggio": 1}'):
        os.environ["MEMORY_FLUSH_JUDGE_STUB"] = risposta_giudice
        blocco, fermati = mf.filter_duplicates(v, cand_listino())
        check("390, 590 e 990" in blocco and fermati == [], risposta_giudice)
    os.environ["MEMORY_FLUSH_JUDGE_STUB"] = "Ecco il verdetto: " + SI_C1 + " spero vada bene"
    blocco, fermati = mf.filter_duplicates(v, cand_listino())
    check(blocco == "" and len(fermati) == 1)


@prova("M20 doppione di una voce gia' in coda")
def _():
    in_coda = CODA_KIT.replace("_Nessun candidato in coda._", cand_listino("02-memoria/me.md"))
    v = nuovo_vault(coda=in_coda)
    scrivi(v / "10-lavoro/progetto/MEMORY.md", "# Dossier\n\nNessun listino deciso ancora per questo progetto.\n")
    os.environ["MEMORY_FLUSH_JUDGE_STUB"] = SI_C1
    blocco, fermati = mf.filter_duplicates(v, cand_listino("02-memoria/me.md"))
    check(blocco == "" and len(fermati) == 1, str(fermati))
    check(fermati[0][1] == "02-memoria/PROMOTE-QUEUE.md (voce già in coda n. 1)", fermati[0][1])


@prova("M40 M41 M55 blocchi senza voci, vuoti, con frase introduttiva")
def _():
    v = vault_listino()
    os.environ["MEMORY_FLUSH_JUDGE_STUB"] = "[]"
    libero = "Testo libero senza intestazioni\nsu due righe "
    check(mf.filter_duplicates(v, libero) == (libero, []))
    check(mf.filter_duplicates(v, "") == ("", []))
    blocco, fermati = mf.filter_duplicates(v, "Ecco i candidati:\n\n" + CAND_CARTO + "\n\n")
    check(blocco == CAND_CARTO and fermati == [])


@prova("M42 M43 M56 + D voci corte, senza somiglianze o solo in fonti escluse: niente giudice")
def _():
    v = nuovo_vault()
    scrivi(v / "01-daily/2030-01-09.md", MEMORY_LISTINO)
    scrivi(v / "10-lavoro/p/knowledge/calls/2030-01-09-call.md", MEMORY_LISTINO)
    scrivi(v / "10-lavoro/p/knowledge/raw/fonte.md", MEMORY_LISTINO)
    scrivi(v / "10-lavoro/p/CLAUDE.md", MEMORY_LISTINO)
    scrivi(v / "00-inbox/nota.md", MEMORY_LISTINO)
    chiamate = cattura_giudice(SI_C1)
    corto = "### [2030-01-10] fatto → wiki globale\n**Proposta:** Tre parole sole.\n**Fonte:** x\n**Stato:** y"
    estraneo = ("### [2030-01-10] fatto → wiki globale\n**Proposta:** Il cavallo bianco attraversava "
                "velocemente montagne innevate durante inverni lunghissimi.\n**Fonte:** x\n**Stato:** y")
    for c in (corto, estraneo, cand_listino()):
        blocco, fermati = mf.filter_duplicates(v, c)
        check(blocco == c and fermati == [])
    check(chiamate == [], "giudice chiamato")


def vault_due_fonti():
    v = vault_listino()
    scrivi(v / "02-memoria/wiki/spedizioni.md",
           "# Spedizioni\n\nLe spedizioni internazionali partono ogni giovedi' tramite corriere "
           "Rapidex con tariffa annuale di 1450 euro.\n")
    return v


CAND_SPEDIZIONI = ("### [2030-01-10] fatto → MEMORY.md di progetto\n"
                   "**Proposta:** Spedizioni internazionali ogni giovedi' tramite corriere Rapidex, tariffa annuale 1450 euro.\n"
                   "**Fonte:** sessione chat 2030-01-10\n**Stato:** da rivedere")


@prova("M44 M54 numerazione solo delle voci inviate; blocco senza righe vuote agli estremi")
def _():
    v = vault_due_fonti()
    chiamate = cattura_giudice('[{"id": "C1", "gia_scritto": false, "passaggio": 0}, '
                               '{"id": "C2", "gia_scritto": true, "passaggio": 1}]')
    blocco, fermati = mf.filter_duplicates(v, "\n".join([cand_listino(), "", CAND_CARTO, "", CAND_SPEDIZIONI, ""]))
    check(len(chiamate) == 1)
    check("=== CANDIDATO C2 ===" in chiamate[0] and "=== CANDIDATO C3 ===" not in chiamate[0])
    check(fermati and fermati[0][1] == "02-memoria/wiki/spedizioni.md", str(fermati))
    check(blocco == cand_listino() + "\n\n" + CAND_CARTO, repr(blocco))


@prova("M45 dieci candidati: due lotti, etichette che ripartono da C1")
def _():
    v = vault_listino()
    si_tutti = json.dumps([{"id": "C{}".format(i), "gia_scritto": True, "passaggio": 1} for i in range(1, 9)])
    chiamate = cattura_giudice(si_tutti)
    blocco_in = "\n\n".join(cand_listino(extra=" Variante numero {}.".format(i)) for i in range(10))
    blocco, fermati = mf.filter_duplicates(v, blocco_in)
    check(len(chiamate) == 2, str(len(chiamate)))
    check("=== CANDIDATO C8 ===" in chiamate[0] and "=== CANDIDATO C9 ===" not in chiamate[0])
    check("=== CANDIDATO C2 ===" in chiamate[1] and "=== CANDIDATO C3 ===" not in chiamate[1])
    check(blocco == "" and len(fermati) == 10)


@prova("M49 giudice assente (claude non trovato): nessun fermato")
def _():
    v = vault_listino()
    mf._esegui_claude = ORIGINALI["_esegui_claude"]
    mf.POSTI_COMUNI = ["~/.local/bin/claude"]
    os.environ["PATH"] = str(cartella())
    os.environ["HOME"] = str(cartella())
    blocco, fermati = mf.filter_duplicates(v, cand_listino())
    check(blocco == cand_listino() and fermati == [])


@prova("M50 solo la risposta finta del riassunto: giudice muto, nessuna chiamata")
def _():
    v = vault_listino()
    os.environ["MEMORY_FLUSH_STUB"] = risposta()
    blocco, fermati = mf.filter_duplicates(v, cand_listino())
    check(blocco == cand_listino() and fermati == [])
    check(VIOLAZIONI == [])


@prova("M51 M52 M53 regola del livello: wiki globale e wiki di progetto")
def _():
    os.environ["MEMORY_FLUSH_JUDGE_STUB"] = SI_C1
    v = vault_listino("02-memoria/wiki/pagina.md")
    blocco, fermati = mf.filter_duplicates(v, cand_listino("wiki globale 02-memoria/wiki/listini.md"))
    check(blocco == "" and fermati[0][1] == "02-memoria/wiki/pagina.md")
    blocco, fermati = mf.filter_duplicates(v, cand_listino())
    check(blocco == "" and fermati[0][1] == "02-memoria/wiki/pagina.md")
    v = vault_listino("10-lavoro/p/knowledge/wiki/pagina.md")
    blocco, fermati = mf.filter_duplicates(v, cand_listino("wiki globale"))
    check(blocco == cand_listino("wiki globale") and fermati == [])
    blocco, fermati = mf.filter_duplicates(v, cand_listino("wiki di progetto p"))
    check(blocco == "" and fermati[0][1] == "10-lavoro/p/knowledge/wiki/pagina.md")
    # M53: destinato a MEMORY.md di progetto, gia' scritto in un'ancora in radice
    for ancora in ("CLAUDE.md", "CAPISALDI.md", "ARCHITETTURA.md"):
        v = vault_listino(ancora)
        blocco, fermati = mf.filter_duplicates(v, cand_listino())
        check(blocco == "" and fermati[0][1] == ancora, ancora)
        blocco, fermati = mf.filter_duplicates(v, cand_listino("02-memoria/me.md"))
        check(blocco == "" and fermati[0][1] == ancora, "globale " + ancora)


@prova("M57 + D voci in coda: citazione col pallino blu e esempio nel commento non contano")
def _():
    check(mf._voci_in_coda(CODA_KIT) == [])
    marcata = cand_listino("02-memoria/me.md") + "\n> \U0001F535 tenuta per l utente: decisione ancora in ballo"
    voci = mf._voci_in_coda(CODA_KIT.replace("_Nessun candidato in coda._", marcata))
    check(len(voci) == 1 and "tenuta" not in voci[0][1] and "390, 590 e 990" in voci[0][1])
    check("Fonte" not in voci[0][1] and "2030-01-10" not in voci[0][1])


@prova("D errore nella costruzione del controllo: blocco intatto")
def _():
    v = vault_listino()
    originale = mf._Indice

    def rotto(radice):
        raise RuntimeError("guasto")
    mf._Indice = rotto
    try:
        check(mf.filter_duplicates(v, cand_listino()) == (cand_listino(), []))
    finally:
        mf._Indice = originale


@prova("D lotto in errore: resta in coda, gli altri proseguono")
def _():
    v = vault_listino()
    si_tutti = json.dumps([{"id": "C{}".format(i), "gia_scritto": True, "passaggio": 1} for i in range(1, 9)])
    chiamate = []

    def finto(richiesta):
        chiamate.append(richiesta)
        if len(chiamate) == 1:
            raise mf.ErroreModello("tempo scaduto")
        return si_tutti
    mf._risposta_giudice = finto
    blocco, fermati = mf.filter_duplicates(v, "\n\n".join(cand_listino(extra=" Variante {}.".format(i)) for i in range(10)))
    check(len(fermati) == 2 and blocco.count("### [") == 8)


# ===========================================================================
# memory_flush.py: inserimento in coda
# ===========================================================================

@prova("M5 insert_candidates: segnaposto via, sezioni successive intatte")
def _():
    q = "# Coda\n\n## In attesa\n\n_Nessun candidato in coda._\n\n---\n\n## Rituale\n\nTesto.\n"
    n = mf.insert_candidates(q, CAND_CARTO)
    check(mf.SEGNAPOSTO_CODA not in n and "Cartotecnica Alfa" in n and "## Rituale" in n)
    check(n.endswith("---\n\n## Rituale\n\nTesto.\n"))


@prova("M58 M59 insert_candidates sul modello del kit, due volte")
def _():
    n1 = mf.insert_candidates(CODA_KIT, CAND_CARTO)
    atteso = CODA_KIT.replace("_Nessun candidato in coda._\n", CAND_CARTO + "\n")
    check(n1 == atteso, n1)
    n2 = mf.insert_candidates(n1, cand_listino())
    check(n2 == CODA_KIT.replace("_Nessun candidato in coda._\n", CAND_CARTO + "\n\n" + cand_listino() + "\n"), n2)


@prova("M60 + D sezione assente: in fondo, oppure prima di Promossi")
def _():
    n = mf.insert_candidates("# Coda\n\nSolo testo.\n", CAND_CARTO)
    check(n == "# Coda\n\nSolo testo.\n\n## In attesa\n\n" + CAND_CARTO + "\n", repr(n))
    q = "# Coda\n\n---\n\n## Promossi (storico)\n\nVecchio.\n"
    n = mf.insert_candidates(q, CAND_CARTO)
    check(n == "# Coda\n\n---\n\n## In attesa\n\n" + CAND_CARTO + "\n\n---\n\n## Promossi (storico)\n\nVecchio.\n", repr(n))


@prova("D confine unico: In attesa senza tre trattini finisce alla successiva ##")
def _():
    q = "# Coda\n\n## In attesa\n\n_Nessun candidato in coda._\n## Promossi\n\nStorico.\n"
    n = mf.insert_candidates(q, CAND_CARTO)
    check(n == "# Coda\n\n## In attesa\n\n" + CAND_CARTO + "\n\n## Promossi\n\nStorico.\n", repr(n))
    q = "# Coda\n\n## In attesa\n\n### [2030-01-01] fatto → x\n**Proposta:** y"
    n = mf.insert_candidates(q, CAND_CARTO)
    check(n == q + "\n\n" + CAND_CARTO + "\n", repr(n))
    check(mf.insert_candidates("", CAND_CARTO) == mf.SCHELETRO_CODA.replace("_Nessun candidato in coda._\n", CAND_CARTO + "\n"))


# ===========================================================================
# memory_flush.py: run
# ===========================================================================

@prova("M6 M7 M63 M66 M69 run riuscito: appunti, coda, registro")
def _():
    v = nuovo_vault()
    os.environ["MEMORY_FLUSH_STUB"] = risposta("- Fissato il listino a tre fasce", CAND_CARTO)
    check(mf.run("session_end", trascrizione_lunga(), "a1b2c3d4e5f6") == 0)
    a = shared.read_text(appunti(v))
    check(a.startswith("# Daily {}\n## Flush sessione, ".format(oggi())), a)
    check("· session_end\n\n- Fissato il listino a tre fasce\n\n" in a and a.endswith("\n\n"))
    check("Non accodati alla coda memoria" not in a)
    q = coda(v)
    check("Cartotecnica Alfa" in q and mf.SEGNAPOSTO_CODA not in q)
    log = registro(v)
    check(log.startswith("[") and "] ok: daily={}.md candidati+=1 gia_su_disco=0 trigger=session_end session=a1b2c3d4\n".format(oggi()) in log, log)


@prova("M8 M70 run su trascrizione troppo breve: niente scritto, riga nel registro")
def _():
    v = nuovo_vault()
    os.environ["MEMORY_FLUSH_STUB"] = risposta(candidati=CAND_CARTO)
    t = trascrizione([turno("user", "ok")])
    check(mf.run("session_end", t, "s") == 0)
    check(not appunti(v).exists() and coda(v) == CODA_KIT)
    check("troppo breve (9 char) trigger=session_end" in registro(v), registro(v))  # "[user] ok"


@prova("M18 M19 run con un doppione e una voce nuova")
def _():
    v = vault_listino()
    os.environ["MEMORY_FLUSH_STUB"] = risposta(candidati=cand_listino() + "\n\n" + CAND_CARTO)
    os.environ["MEMORY_FLUSH_JUDGE_STUB"] = ('[{"id": "C1", "gia_scritto": true, "passaggio": 1}, '
                                             '{"id": "C2", "gia_scritto": false, "passaggio": 0}]')
    check(mf.run("session_end", trascrizione_lunga(), "s") == 0)
    q = coda(v)
    check("Cartotecnica Alfa" in q and "390, 590 e 990" not in q)
    a = shared.read_text(appunti(v))
    check("**Non accodati alla coda memoria perché già su disco:**\n- decisione → MEMORY.md di progetto Listino" in a, a)
    check("→ `10-lavoro/progetto/MEMORY.md`\n\n" in a)
    check("gia_su_disco=1" in registro(v))


@prova("M61 coda assente: creata dallo scheletro")
def _():
    v = nuovo_vault(coda=None)
    os.environ["MEMORY_FLUSH_STUB"] = risposta(candidati=CAND_CARTO)
    check(mf.run("session_end", trascrizione_lunga(), "s") == 0)
    q = coda(v)
    check(q.startswith("# PROMOTE-QUEUE: candidati alla memoria\n") and "## In attesa" in q)
    check("Cartotecnica Alfa" in q and mf.SEGNAPOSTO_CODA not in q)


@prova("M62 NONE: appunti scritti, coda non toccata")
def _():
    v = nuovo_vault()
    q = v / "02-memoria" / "PROMOTE-QUEUE.md"
    os.utime(str(q), (1000000000, 1000000000))
    prima = q.stat().st_mtime_ns
    os.environ["MEMORY_FLUSH_STUB"] = risposta(candidati="NONE")
    check(mf.run("session_end", trascrizione_lunga(), "s") == 0)
    check(appunti(v).exists() and q.stat().st_mtime_ns == prima and coda(v) == CODA_KIT)


@prova("M64 M65 secondo run nello stesso giorno, innesco pre_compact")
def _():
    v = nuovo_vault()
    os.environ["MEMORY_FLUSH_STUB"] = risposta("- Primo blocco")
    mf.run("session_end", trascrizione_lunga(), "s")
    os.environ["MEMORY_FLUSH_STUB"] = risposta("- Secondo blocco")
    mf.run("pre_compact", trascrizione_lunga(), "s")
    a = shared.read_text(appunti(v))
    check(a.count("# Daily ") == 1 and a.count("## Flush sessione, ") == 2)
    check(a.index("- Primo blocco") < a.index("· pre_compact") < a.index("- Secondo blocco"))


@prova("D appunti scritti a mano senza a capo finale: il blocco parte su riga nuova")
def _():
    v = nuovo_vault()
    scrivi(appunti(v), "# Daily mio\nnota a mano")
    os.environ["MEMORY_FLUSH_STUB"] = risposta()
    mf.run("session_end", trascrizione_lunga(), "s")
    check(shared.read_text(appunti(v)).startswith("# Daily mio\nnota a mano\n## Flush sessione, "))


@prova("M67 risposta finta vuota: niente scritto, riga nessun riassunto")
def _():
    v = nuovo_vault()
    os.environ["MEMORY_FLUSH_STUB"] = ""
    check(mf.run("session_end", trascrizione_lunga(), "s") == 0)
    check(not appunti(v).exists() and coda(v) == CODA_KIT)
    check("nessun riassunto" in registro(v))


@prova("D riassunto vuoto ma candidati presenti: si accodano")
def _():
    v = nuovo_vault()
    os.environ["MEMORY_FLUSH_STUB"] = "===DAILY===\n\n===CANDIDATES===\n" + CAND_CARTO
    check(mf.run("session_end", trascrizione_lunga(), "s") == 0)
    check("Cartotecnica Alfa" in coda(v))
    os.environ["MEMORY_FLUSH_STUB"] = "===DAILY===\n\n===CANDIDATES===\nNONE"
    v = nuovo_vault()
    check(mf.run("session_end", trascrizione_lunga(), "s") == 0)
    check(not appunti(v).exists() and "nessun riassunto" in registro(v))


@prova("D risposta senza marcatori: niente appunti, errore nel registro e in audit-log")
def _():
    v = nuovo_vault()
    os.environ["MEMORY_FLUSH_STUB"] = "Ho riassunto la sessione ma ho dimenticato il formato."
    check(mf.run("session_end", trascrizione_lunga(), "abcdefghij") == 1)
    check(not appunti(v).exists() and coda(v) == CODA_KIT)
    check("ERRORE" in registro(v))
    audit = shared.read_text(v / "audit-log.md")
    check("memory_flush" in audit and "session=abcdefgh" in audit and audit.endswith("\n"), audit)


@prova("M68 + D claude assente: uscita 1, niente scritto, errore in registro e audit-log")
def _():
    v = nuovo_vault()
    mf._esegui_claude = ORIGINALI["_esegui_claude"]
    mf.POSTI_COMUNI = ["~/.local/bin/claude"]
    os.environ["PATH"] = str(cartella())
    os.environ["HOME"] = str(cartella())
    check(mf.run("session_end", trascrizione_lunga(), "s") == 1)
    check(not appunti(v).exists() and coda(v) == CODA_KIT)
    log = registro(v)
    check("ERRORE riassunto" in log and "non trovato" in log and "posti comuni" in log, log)
    check("non trovato" in shared.read_text(v / "audit-log.md"))


@prova("M75 M76 finto claude in ~/.local/bin: trovato, haiku, strumenti negati, freno, giudice")
def _():
    v = vault_listino()
    casa = cartella()
    annotazioni = cartella() / "chiamate.jsonl"
    finto_claude(casa / ".local" / "bin", annotazioni)
    mf._esegui_claude = ORIGINALI["_esegui_claude"]
    os.environ["PATH"] = str(cartella())
    os.environ["HOME"] = str(casa)
    check(mf.run("session_end", trascrizione_lunga(), "s") == 0)
    chiamate = [json.loads(r) for r in annotazioni.read_text().splitlines()]
    check(len(chiamate) == 1, str(chiamate))
    a = chiamate[0]["argv"]
    check(chiamate[0]["invoked"] == "flush")
    check(a[0] == "-p" and a[a.index("--model") + 1] == "haiku")
    check(a[a.index("--disallowedTools") + 1:] == mf.STRUMENTI_NEGATI, str(a))
    check("--setting-sources" not in a and "--no-session-persistence" not in a)
    check("Cartotecnica Alfa" in coda(v))
    annotazioni.write_text("")
    mf.filter_duplicates(v, cand_listino())
    giudice = [json.loads(r) for r in annotazioni.read_text().splitlines()]
    check(len(giudice) == 1, str(giudice))
    g = giudice[0]["argv"]
    check(g[g.index("--setting-sources") + 1] == "user" and "--no-session-persistence" in g)
    check(g[g.index("--disallowedTools") + 1:] == mf.STRUMENTI_NEGATI)
    check(giudice[0]["invoked"] == "flush")


@prova("M74 CLAUDE_PROJECT_DIR cambiata fra due run")
def _():
    v1 = nuovo_vault()
    os.environ["MEMORY_FLUSH_STUB"] = risposta("- Nel primo vault")
    mf.run("session_end", trascrizione_lunga(), "s")
    v2 = nuovo_vault()
    os.environ["MEMORY_FLUSH_STUB"] = risposta("- Nel secondo vault")
    mf.run("session_end", trascrizione_lunga(), "s")
    check("Nel secondo vault" in shared.read_text(appunti(v2)))
    check("Nel secondo vault" not in shared.read_text(appunti(v1)))


@prova("M71 M72 M73 riga di comando: opzioni, nessuna opzione, opzione sconosciuta")
def _():
    v = nuovo_vault()
    prog = str(SCRIPTS / "memory_flush.py")
    r = lancia([PY, prog, "--trigger", "pre_compact", "--transcript", trascrizione_lunga(), "--session-id", "zzzzyyyyxxxx"],
               env=ambiente_figlio(MEMORY_FLUSH_STUB=risposta("- Dal programma")))
    check(r.returncode == 0 and r.stdout == b"" and r.stderr == b"", r.stderr.decode())
    check("· pre_compact" in shared.read_text(appunti(v)) and "session=zzzzyyyy" in registro(v))
    r = lancia([PY, prog, "--transcript", trascrizione_lunga()], env=ambiente_figlio(MEMORY_FLUSH_STUB="senza marcatori"))
    check(r.returncode == 1)
    v = nuovo_vault()
    r = lancia([PY, prog])
    check(r.returncode == 0 and "troppo breve (0 char)" in registro(v))
    r = lancia([PY, prog, "--sconosciuta", "x"])
    check(r.returncode == 2 and b"usage" in r.stderr.lower())


@prova("D blocco degli appunti non ottenuto: errore, coda non scritta, audit-log")
def _():
    v = nuovo_vault()
    os.environ["MEMORY_FLUSH_STUB"] = risposta(candidati=CAND_CARTO)

    def occupato(*a, **k):
        raise TimeoutError("blocco di appunti non ottenuto entro 10 secondi")
    shared.append_block = occupato
    try:
        mf.run("session_end", trascrizione_lunga(), "s")
        check(False, "nessun errore")
    except TimeoutError:
        pass
    check(coda(v) == CODA_KIT and "ERRORE" in registro(v))


# ===========================================================================
# Vincoli sui file
# ===========================================================================

@prova("D intestazione di licenza e nessun trattino lungo nei file")
def _():
    files = [SCRIPTS / "shared.py", SCRIPTS / "memory_flush.py", HOOKS / "session-end-flush.py",
             HOOKS / "pre-compact-flush.py", Path(__file__).resolve()]
    for f in files:
        testo = f.read_text(encoding="utf-8")
        check(testo.startswith(INTESTAZIONE + "\n# Vedi LICENZA.md nella radice del vault.\n"), f.name)
        check(TRATTINO_LUNGO not in testo, f.name)


# ===========================================================================
# Esecuzione
# ===========================================================================

ORIGINALI = {n: getattr(mf, n) for n in ("_esegui_claude", "_risposta_giudice", "_risposta_riassunto", "POSTI_COMUNI")}
ORIGINALI_SHARED = {n: getattr(shared, n) for n in ("append_block",)}


def _vietato(richiesta, opzioni_extra=()):
    VIOLAZIONI.append(richiesta[:80])
    raise mf.ErroreModello("chiamata vera a claude vietata nelle prove")


def main():
    for k in ("MEMORY_FLUSH_STUB", "MEMORY_FLUSH_JUDGE_STUB", "CLAUDE_INVOKED_BY"):
        os.environ.pop(k, None)
    iniziale = os.environ.copy()
    cwd = os.getcwd()
    passate = 0
    for nome, f in PROVE:
        os.environ.clear()
        os.environ.update(iniziale)
        os.chdir(cwd)
        for n, val in ORIGINALI.items():
            setattr(mf, n, val)
        for n, val in ORIGINALI_SHARED.items():
            setattr(shared, n, val)
        mf._esegui_claude = _vietato
        del VIOLAZIONI[:]
        try:
            f()
            check(VIOLAZIONI == [], "tentata una chiamata vera a claude")
            passate += 1
            print("ok      " + nome)
        except Exception as e:
            print("FALLITA " + nome + ": " + repr(e)[:500])
            traceback.print_exc(limit=3)
    os.chdir(cwd)
    os.environ.clear()
    os.environ.update(iniziale)
    for n, val in ORIGINALI.items():
        setattr(mf, n, val)
    shutil.rmtree(str(BASE), ignore_errors=True)
    print("{}/{} test passati".format(passate, len(PROVE)))
    return 0 if passate == len(PROVE) else 1


if __name__ == "__main__":
    sys.exit(main())
