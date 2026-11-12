# 2nd Brain Hero Mode · Copyright (c) 2026 Alessandro Pacifico (Pacibrand).
# Vedi LICENZA.md nella radice del vault.
"""Libreria comune degli script del vault.

Offre tre cose:
- dove sta la radice del vault (`vault_root`);
- lettura che non va mai in errore e scritture protette da un blocco fra processi
  (`read_text`, `append_text`, `write_text_atomic`, piu' `update_text` per leggere,
  cambiare e riscrivere un file sotto un unico blocco);
- il lancio in sottofondo del salvataggio della memoria (`launch_flush`) e il freno
  alla ricorsione (`invoked_by_flush`).

Si importa con il nome `shared`. L'importazione non crea file, non stampa e non legge
l'ambiente: ogni funzione legge cio' che le serve al momento della chiamata.
Solo macOS e Linux: il blocco usa `fcntl.flock`.
"""

import contextlib
import fcntl
import hashlib
import os
import subprocess
import sys
import time
from pathlib import Path

# Valori di CLAUDE_INVOKED_BY che indicano un Claude lanciato da uno script del vault:
# per questi non si fa partire il salvataggio della memoria.
_CLAUDE_DI_SERVIZIO = frozenset({"flush", "mail-sync", "guard"})

# Ogni quanto si riprova a prendere un blocco occupato, in secondi.
_INTERVALLO_RIPROVA = 0.1


# ---------------------------------------------------------------------------
# Radice del vault e lettura
# ---------------------------------------------------------------------------

def vault_root():
    """Radice del vault: CLAUDE_PROJECT_DIR se c'e' (e non e' vuota), altrimenti la
    cartella corrente. Letta a ogni chiamata, senza controllare che esista."""
    indicata = os.environ.get("CLAUDE_PROJECT_DIR")
    if indicata:
        return Path(indicata)
    return Path(os.getcwd())


def read_text(path):
    """Contenuto UTF-8 del file; stringa vuota se assente, illeggibile o non UTF-8."""
    try:
        with open(path, "r", encoding="utf-8", newline="") as f:
            return f.read()
    except (OSError, UnicodeDecodeError, ValueError, TypeError):
        return ""


# ---------------------------------------------------------------------------
# Blocco fra processi
# ---------------------------------------------------------------------------

def _file_di_blocco(path):
    """File di blocco del bersaglio, nella cartella dei blocchi del vault corrente.

    Il nome unisce il nome del bersaglio e un'impronta del suo percorso assoluto, cosi'
    due file omonimi in cartelle diverse non condividono il blocco."""
    assoluto = Path(os.path.abspath(str(path)))
    try:
        assoluto = assoluto.resolve()
    except (OSError, RuntimeError):
        pass
    impronta = hashlib.sha256(str(assoluto).encode("utf-8")).hexdigest()[:16]
    cartella = vault_root() / ".claude" / "data" / "locks"
    return cartella / "{}.{}.lock".format(assoluto.name, impronta)


@contextlib.contextmanager
def file_lock(path, timeout=10.0):
    """Tiene il blocco esclusivo legato a `path` per la durata del `with`.

    Se il blocco e' occupato riprova ogni decimo di secondo fino a `timeout` secondi,
    poi solleva TimeoutError. Il blocco non e' rientrante. Si libera all'uscita dal
    `with`, anche in caso di errore, e da solo se il processo muore."""
    blocco = _file_di_blocco(path)
    blocco.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(blocco), os.O_RDWR | os.O_CREAT, 0o644)
    try:
        scadenza = time.monotonic() + float(timeout)
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except (BlockingIOError, PermissionError):
                if time.monotonic() >= scadenza:
                    raise TimeoutError(
                        "blocco di {} non ottenuto entro {} secondi".format(path, timeout)
                    )
                time.sleep(_INTERVALLO_RIPROVA)
        try:
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


# ---------------------------------------------------------------------------
# Scritture
# ---------------------------------------------------------------------------

def _aggiungi_senza_blocco(path, text):
    """Aggiunge `text` in fondo al file, creando cartelle e file se mancano.
    Da chiamare solo tenendo gia' il blocco del file."""
    bersaglio = Path(path)
    bersaglio.parent.mkdir(parents=True, exist_ok=True)
    with open(bersaglio, "a", encoding="utf-8", newline="") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())


def _sostituisci_senza_blocco(path, text):
    """Sostituisce l'intero contenuto del file in un colpo solo: scrive un temporaneo
    nascosto accanto al bersaglio (`.<nome>.tmp`) e poi lo scambia col bersaglio.
    Da chiamare solo tenendo gia' il blocco del file."""
    bersaglio = Path(path)
    bersaglio.parent.mkdir(parents=True, exist_ok=True)
    temporaneo = bersaglio.parent / ".{}.tmp".format(bersaglio.name)
    with open(temporaneo, "w", encoding="utf-8", newline="") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(str(temporaneo), str(bersaglio))


def append_text(path, text, timeout=10.0):
    """Aggiunge `text` in fondo al file, sotto blocco. Nessun a capo aggiunto."""
    with file_lock(path, timeout):
        _aggiungi_senza_blocco(path, text)


def write_text_atomic(path, text, timeout=10.0):
    """Sostituisce l'intero contenuto del file con `text`, sotto blocco: chi legge vede
    sempre la versione vecchia intera o la nuova intera."""
    with file_lock(path, timeout):
        _sostituisci_senza_blocco(path, text)


def update_text(path, trasforma, timeout=10.0):
    """Legge il file, calcola il testo nuovo con `trasforma(vecchio)` e lo riscrive in
    modo atomico, tutto sotto un unico blocco: due aggiornamenti in parallelo non si
    cancellano a vicenda. Se il testo non cambia il file non viene toccato.
    Restituisce il testo nuovo."""
    with file_lock(path, timeout):
        vecchio = read_text(path)
        nuovo = trasforma(vecchio)
        if nuovo != vecchio or not Path(path).exists():
            _sostituisci_senza_blocco(path, nuovo)
        return nuovo


def append_block(path, text, header_if_new="", timeout=10.0):
    """Aggiunge un blocco in fondo al file, sotto blocco, con due accortezze per i file
    di appunti: se il file non esiste scrive prima `header_if_new`; se esiste e non
    finisce con un a capo, ne mette uno prima del blocco."""
    with file_lock(path, timeout):
        bersaglio = Path(path)
        if not bersaglio.exists():
            pezzo = header_if_new + text
        else:
            attuale = read_text(bersaglio)
            pezzo = text if (not attuale or attuale.endswith("\n")) else "\n" + text
        _aggiungi_senza_blocco(bersaglio, pezzo)


# ---------------------------------------------------------------------------
# Salvataggio della memoria
# ---------------------------------------------------------------------------

def invoked_by_flush():
    """Vero se questo processo gira dentro un Claude lanciato da uno script del vault
    (salvataggio, giro posta, guardia): in quel caso il salvataggio non riparte."""
    return os.environ.get("CLAUDE_INVOKED_BY", "") in _CLAUDE_DI_SERVIZIO


def _come_testo(valore):
    return "" if valore is None else str(valore)


def launch_flush(trigger, transcript_path, session_id):
    """Fa partire `memory_flush.py` del vault corrente in sottofondo e torna subito.

    Il processo e' staccato (sessione nuova), lavora nella radice del vault, ha
    CLAUDE_INVOKED_BY=flush e scrive output ed errori in `.claude/data/flush/flush.log`.
    Restituisce False se il programma non c'e' (e in quel caso non crea nulla)."""
    radice = vault_root()
    programma = radice / ".claude" / "scripts" / "memory_flush.py"
    if not programma.is_file():
        return False

    cartella_registro = radice / ".claude" / "data" / "flush"
    cartella_registro.mkdir(parents=True, exist_ok=True)

    ambiente = dict(os.environ)
    ambiente["CLAUDE_INVOKED_BY"] = "flush"
    comando = [
        sys.executable, str(programma),
        "--trigger", _come_testo(trigger),
        "--transcript", _come_testo(transcript_path),
        "--session-id", _come_testo(session_id),
    ]
    with open(cartella_registro / "flush.log", "ab") as registro:
        subprocess.Popen(
            comando,
            cwd=str(radice),
            env=ambiente,
            stdin=subprocess.DEVNULL,
            stdout=registro,
            stderr=registro,
            start_new_session=True,
            close_fds=True,
        )
    # Il figlio ha la sua copia del descrittore: chiudere il nostro non lo tocca.
    return True
