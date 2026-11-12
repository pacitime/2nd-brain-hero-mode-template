#!/usr/bin/env python3
# 2nd Brain Hero Mode · Copyright (c) 2026 Alessandro Pacifico (Pacibrand).
# Vedi LICENZA.md nella radice del vault.
"""Hook PreToolUse che tiene chiavi e credenziali fuori dal contesto di Claude.

Tre famiglie di controlli:
- segreti: niente lettura, stampa, copia o registrazione di file d'ambiente, chiavi e
  credenziali, ne' dell'ambiente stesso;
- cancellazioni: niente cancellazioni ricorsive, forzate, con jolly o di massa;
- scrittura fuori dal vault: Edit e Write lavorano solo dentro la radice del vault.

Uso come hook: legge un oggetto JSON da stdin, esce con 0 (passa) o 2 (blocca, motivo su
stderr). Uso come libreria: `check_bash_command(command)` ritorna il motivo se il comando
sarebbe bloccato, altrimenti None. Caricare il file come modulo non legge stdin e non stampa.

Nota per chi legge il sorgente: l'hook attivo nel vault rifiuta i file che contengono certe
sequenze (il nome del comando che stampa l'ambiente, stampe dell'ambiente in Python e simili).
Per questo alcune parole qui sotto sono composte a pezzi: il significato non cambia.
"""

import fnmatch
import json
import os
import re
import shlex
import sys

# ---------------------------------------------------------------------------
# Parole composte a pezzi (vedi la nota in testa al file).
# ---------------------------------------------------------------------------
_STAMPA = "pri" "nt"                      # il nome della funzione di stampa
_CMD_STAMPA_AMBIENTE = _STAMPA + "env"    # print + env, il comando che stampa l'ambiente
_CONSOLE = "con" "sole"
_JSON = "js" "on"

_W = "a-z0-9_"                            # caratteri di parola (sul testo gia' minuscolo)


def _parola(nome):
    """Regex per `nome` come parola intera (testo gia' in minuscolo)."""
    return r"(?<![a-z0-9_])" + nome + r"(?![a-z0-9_])"


# ---------------------------------------------------------------------------
# Messaggi
# ---------------------------------------------------------------------------
_TESTATA = "BLOCCO DI SICUREZZA (block-secrets)"

_PRINCIPI = {
    "segreto": (
        "Principio: chiavi e credenziali non devono entrare nel contesto di Claude. "
        "Eseguire uno script che usa una chiave va bene; leggerla, stamparla, copiarla o "
        "registrarla dove Claude la vede no."
    ),
    "riservata": (
        "Principio: la cartella _local-only resta fuori dal contesto. Dalla shell si puo' "
        "solo elencarla (ls, du) senza pipe ne' redirezioni; le call riservate si leggono con Read."
    ),
    "cancellazione": (
        "Principio: le cancellazioni ricorsive, forzate, con jolly o di massa e le operazioni "
        "git che buttano via lavoro le fa l'utente a mano dal terminale. Cancellare un singolo "
        "file con nome esplicito resta permesso."
    ),
    "fuori": (
        "Principio: Edit e Write lavorano solo dentro la cartella del vault. Se serve un file "
        "fuori, lo copia l'utente."
    ),
    "ingresso": (
        "Principio: un ingresso che non si riesce a leggere non si lascia passare alla cieca."
    ),
}

_TITOLI = {
    "segreto": "possibile esposizione di un segreto",
    "riservata": "cartella riservata",
    "cancellazione": "cancellazione o operazione distruttiva",
    "fuori": "scrittura fuori dalla cartella del vault",
    "ingresso": "ingresso dell'hook non valido",
}


def _messaggio(categoria, motivo):
    return "%s: %s.\nMotivo: %s.\n%s" % (
        _TESTATA, _TITOLI[categoria], motivo, _PRINCIPI[categoria])


class _FormaInattesa(Exception):
    """JSON valido ma di forma che l'hook non sa leggere."""


# ---------------------------------------------------------------------------
# File sensibili
# ---------------------------------------------------------------------------
_MODELLO_DOPO_ENV = re.compile(r"\.(?:example|sample)(?![a-z0-9_])")


def _env_non_modello(testo, intero=False, fine_o_punto=False):
    """Vero se `testo` (minuscolo) contiene un `.env` che non e' un modello d'esempio.

    `intero`: il `.env` non deve essere seguito da un carattere di parola.
    `fine_o_punto`: il `.env` deve stare in fondo o essere seguito da un punto.
    `.env.example` e `.env.sample` sono modelli senza segreti e non contano mai.
    """
    for m in re.finditer(r"\.env", testo):
        dopo = testo[m.end():]
        if _MODELLO_DOPO_ENV.match(dopo):
            continue
        if intero and re.match(r"[a-z0-9_]", dopo):
            continue
        if fine_o_punto and not (dopo == "" or dopo.startswith(".")):
            continue
        return True
    return False


_ESENTI_SECRET = (".md", ".py", ".txt")


def _categoria_file(percorso, per_shell=False):
    """Ritorna la categoria se il percorso e' sensibile, altrimenti None.

    `per_shell`: valutazione di una parola di un comando. La cartella riservata qui non
    conta (la gestiscono le regole proprie della shell) e la regola su «secret» vale solo
    per parole che hanno l'aspetto di un percorso, per non scattare su un testo qualunque.
    """
    p = percorso.lower()
    if not per_shell and ("_local-only/" in p or p.endswith("_local-only")):
        return "cartella riservata _local-only"
    if _env_non_modello(p, fine_o_punto=True):
        return "file d'ambiente"
    if p.endswith(".pem"):
        return "certificato o chiave (.pem)"
    if p.endswith(".key"):
        return "chiave privata (.key)"
    if "credentials.json" in p:
        return "file di credenziali"
    if "google_token.json" in p:
        return "token Google"
    if "master.env" in p:
        return "file d'ambiente principale"
    if re.search(r"\.ssh(?:/|$)", p):
        return "cartella SSH"
    if re.search(r"(?:^|/)id_(?:rsa|ed25519|ecdsa|dsa)", p):
        return "chiave SSH"
    if ".aws/credentials" in p:
        return "credenziali AWS"
    if ".netrc" in p:
        return "file .netrc"
    if "secret" in p and not p.endswith(_ESENTI_SECRET):
        if not per_shell or (("/" in p or "." in p) and " " not in p):
            return "file con «secret» nel nome"
    return None


# ---------------------------------------------------------------------------
# Read: eccezione delle call riservate
# ---------------------------------------------------------------------------
def _radice():
    return os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()


def _call_riservata(percorso):
    """Vero se `percorso` e' una call .md direttamente dentro <radice>/_local-only/calls."""
    try:
        assoluto = percorso if os.path.isabs(percorso) else os.path.join(os.getcwd(), percorso)
        reale = os.path.realpath(assoluto)
        cartella = os.path.realpath(os.path.join(_radice(), "_local-only", "calls"))
        if os.path.dirname(reale) != cartella:
            return False
        if not reale.lower().endswith(".md"):
            return False
        if os.path.exists(reale):
            if os.stat(reale).st_nlink != 1:
                return False
        return True
    except (OSError, ValueError):
        return False


# ---------------------------------------------------------------------------
# Edit e Write: fuori dal vault
# ---------------------------------------------------------------------------
def _fuori_dal_vault(percorso):
    """Vero se il percorso, risolto davvero, non sta dentro la radice del vault."""
    p = os.path.expanduser(percorso)
    if not os.path.isabs(p):
        p = os.path.join(os.getcwd(), p)
    reale = os.path.realpath(p)
    radice = os.path.realpath(_radice())
    if reale == radice:
        return False
    return not reale.startswith(radice.rstrip(os.sep) + os.sep)


# ---------------------------------------------------------------------------
# Edit e Write: testo scritto (solo file di codice)
# ---------------------------------------------------------------------------
_EST_SHELL = (".sh", ".bash", ".zsh")
_EST_CODICE = (".py", ".js", ".ts", ".mjs", ".rb", ".pl") + _EST_SHELL

# Chiamate che mostrano qualcosa (stampa o registro).
_RE_MOSTRA = re.compile(
    r"(?<![a-z0-9_.])(?:p?" + _STAMPA + r"|puts|pp|say|printf)(?![a-z0-9_])"
    r"|(?<![a-z0-9_])(?:logging|logger|log|_log)\.[a-z_]+\s*\("
    r"|sys\.std(?:out|err)\.write\s*\("
    r"|" + _CONSOLE + r"\.[a-z]+\s*\("
    r"|process\.std(?:out|err)\.write\s*\("
)
# Chiamate che serializzano.
_RE_SERIALIZZA = re.compile(
    _JSON + r"\.dumps?\s*\("
    r"|" + _JSON + r"\.stringify\s*\("
    r"|yaml\.(?:safe_)?dump\s*\("
    r"|pickle\.dumps?\s*\("
    r"|marshal\.dumps?\s*\("
)
# Accessi all'ambiente.
_RE_AMBIENTE = re.compile(
    r"os\.environ|getenv\s*\(|environ\.get|process\.env(?![a-z0-9_])"
    r"|(?<![a-z0-9_])env\[|\$env\{|%env(?![a-z0-9_])|(?:deno|bun)\.env"
    r"|(?<![a-z0-9_])env\.(?:fetch|to_h)|dotenv_values\s*\("
)
_RE_LETTURA_FILE = re.compile(
    r"open\s*\(|read_text\s*\(|\.read\s*\(|readfilesync\s*\(|dotenv_values\s*\(")


def _riga_codice_espone(riga):
    """Motivo se una riga di codice (non shell) mostra o serializza l'ambiente."""
    basso = riga.lower()
    for regex, cosa in ((_RE_MOSTRA, "stampa o registra"), (_RE_SERIALIZZA, "serializza")):
        for m in regex.finditer(basso):
            dopo = basso[m.end():]
            dopo_orig = riga[m.end():]
            if _RE_AMBIENTE.search(dopo) or re.search(r"(?<![A-Za-z0-9_])ENV(?![A-Za-z0-9_])", dopo_orig):
                return "il codice %s l'ambiente o una sua variabile" % cosa
            if _env_non_modello(dopo, intero=True) and _RE_LETTURA_FILE.search(dopo):
                return "il codice %s il contenuto di un file .env" % cosa
    return None


def _testo_espone(percorso, testo):
    """Motivo se il testo scritto in un file di codice espone segreti, altrimenti None."""
    est = percorso.lower()
    if not est.endswith(_EST_CODICE):
        return None
    if re.search(_parola(_CMD_STAMPA_AMBIENTE), testo.lower()):
        return "il codice usa il comando che stampa tutto l'ambiente"
    shell = est.endswith(_EST_SHELL)
    for riga in testo.split("\n"):
        if shell:
            if riga.lstrip().startswith("#"):
                continue
            esito = _esamina_righe_shell(riga, modo_testo=True, profondita=0)
            if esito:
                return "lo script " + esito[1]
        else:
            motivo = _riga_codice_espone(riga)
            if motivo:
                return motivo
    return None


# ---------------------------------------------------------------------------
# Shell: strumenti di analisi
# ---------------------------------------------------------------------------
def _dividi_comandi(testo):
    """Divide il testo in comandi semplici su ; & | a capo e parentesi, fuori dagli apici.

    Gli apici inversi e i doppi apici non si spezzano: il loro interno lo valuta la regola
    delle sostituzioni di comando.
    """
    pezzi, buf, apice = [], [], None
    i, n = 0, len(testo)
    while i < n:
        c = testo[i]
        if apice:
            buf.append(c)
            if c == "\\" and apice != "'" and i + 1 < n:
                buf.append(testo[i + 1])
                i += 2
                continue
            if c == apice:
                apice = None
            i += 1
            continue
        if c == "\\" and i + 1 < n:
            buf.append(c)
            buf.append(testo[i + 1])
            i += 2
            continue
        if c in "'\"`":
            apice = c
            buf.append(c)
        elif c in ";&|\n()":
            pezzi.append("".join(buf))
            buf = []
        else:
            buf.append(c)
        i += 1
    pezzi.append("".join(buf))
    return [p.strip() for p in pezzi if p.strip()]


def _parole(comando):
    try:
        return shlex.split(comando)
    except ValueError:
        return comando.split()


_RE_REDIREZIONE = re.compile(r"^(?:\d*|&)(>>|>\||>&|>|<<<|<<-|<<|<>|<&|<)(.*)$")


def _togli_redirezioni(parole):
    """Separa le redirezioni dagli argomenti. Ritorna (argomenti, file letti con <)."""
    resto, ingressi = [], []
    i = 0
    while i < len(parole):
        m = _RE_REDIREZIONE.match(parole[i])
        if m:
            op, dest = m.group(1), m.group(2)
            if not dest and i + 1 < len(parole) and op not in ("<<", "<<-", "<<<"):
                dest = parole[i + 1]
                i += 1
            if op in ("<", "<>"):
                ingressi.append(dest)
            i += 1
            continue
        resto.append(parole[i])
        i += 1
    return resto, ingressi


_PREFISSI = {"if", "then", "else", "elif", "do", "while", "until", "!", "{", "}", "time",
             "exec", "command", "builtin", "nohup", "sudo", "doas"}
_OPZIONI_CON_ARGOMENTO = {"sudo": ("-u", "-g", "-c", "-h", "-p"),
                          "env": ("-u", "-c", "-s", "--unset", "--chdir", "--split-string")}


def _programma(parole):
    """Ritorna (nome del programma in minuscolo, indice) saltando prefissi e assegnazioni.

    `env` seguito da un comando e' un involucro e si salta; `env` senza comando resta `env`.
    """
    i = 0
    while i < len(parole):
        t = parole[i]
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", t):
            i += 1
            continue
        nome = os.path.basename(t).lower() if t not in (".", "[", "[[") else t
        if nome in _PREFISSI or nome == "env":
            con_arg = _OPZIONI_CON_ARGOMENTO.get(nome, ())
            j = i + 1
            while j < len(parole):
                o = parole[j]
                if o.startswith("-") and len(o) > 1:
                    j += 2 if o.lower() in con_arg else 1
                elif nome == "env" and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", o):
                    j += 1
                else:
                    break
            if nome == "env" and j >= len(parole):
                return "env", i
            i = j
            continue
        return nome, i
    return "", len(parole)


# Programmi che nominano un file senza leggerne il contenuto.
_NON_LETTORI = {"ls", "du", "stat", "touch", "mkdir", "cd", "pushd", "echo", "printf",
                "rm", "rmdir", "unlink", "chmod", "chown", "test", "[", "[[", "true", "false",
                "pwd", "which", "file", "wc", "realpath", "readlink", "basename", "dirname",
                "tree"}
_GIT_NON_LETTORI = {"status", "check-ignore", "ls-files"}
_FIND_CHE_AGISCE = {"-exec", "-execdir", "-ok", "-okdir", "-fprint", "-fprint0", "-fprintf",
                    "-fls"}
# Programmi per cui conta anche un `.env` dentro un nome piu' lungo (`.envrc`).
_PROGRAMMI_ENV_LARGO = {"cp", "ln", "xxd", "hexdump", "od", "curl"}
# Programmi che, in un file di script, mostrano il contenuto di un file.
_LETTORI_SCRIPT = {"cat", "head", "tail", "less", "more", "bat", "nl", "strings", "xxd",
                   "od", "hexdump", "base64", "grep", "rg", "awk", "sed", "sort", "tac",
                   "cut", "egrep", "fgrep"}
_GREP = {"grep", "egrep", "fgrep", "rg"}
_SHELL = {"bash", "sh", "zsh", "dash", "ksh"}
_RE_INTERPRETE = re.compile(r"^(?:python[0-9.]*|pypy[0-9.]*|node|nodejs|deno|bun|ruby|perl|php)$")
_RE_OPZIONE_INLINE = re.compile(r"^-[a-z]*[cepr]$")
_RE_TOCCA_AMBIENTE = re.compile(
    r"environ|getenv|dotenv|process\.env|(?<![a-z0-9_])env\[|\$env\{|%env|(?:deno|bun)\.env"
    r"|(?<![a-z0-9_])env\.(?:fetch|to_h)")
_SPIE = ("KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL", "AUTH")
_RE_VARIABILE = re.compile(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)")
_CANDIDATI_JOLLY = (".env", ".env.local", ".env.production", "x.env", "master.env", ".netrc",
                    "id_rsa", "id_rsa.pub", "id_ed25519", "x.pem", "x.key", "credentials.json",
                    "google_token.json")


def _variabile_segreto(testo):
    for m in _RE_VARIABILE.finditer(testo):
        nome = m.group(1).upper()
        if any(s in nome for s in _SPIE):
            return m.group(1)
    return None


def _rischio_jolly(parola):
    """Vero se una parola con caratteri jolly puo' espandersi in un file di segreti."""
    t = parola.lower()
    if re.search(r"\.e(?:\*|\?\?|\[|\$|\\)", t):
        return True
    base = t.rsplit("/", 1)[-1]
    base = re.sub(r"\$\{?[a-z0-9_]*\}?", "*", base)
    if not re.search(r"[*?\[]", base):
        return False
    letterali = re.sub(r"\[[^\]]*\]|[*?]", "", base)
    if len(letterali) < 2:
        return False
    for nome in _CANDIDATI_JOLLY:
        if nome.startswith(".") and not base.startswith("."):
            continue
        if fnmatch.fnmatchcase(nome, base):
            return True
    return False


def _parola_sensibile(parola, programma):
    """Motivo se una parola del comando nomina un file di segreti."""
    pezzi = [parola] + [p for p in re.split(r"[=@<>:,]", parola) if p and p != parola]
    for pezzo in pezzi:
        cat = _categoria_file(pezzo, per_shell=True)
        if cat:
            return "%s: %s" % (cat, pezzo)
        if programma in _PROGRAMMI_ENV_LARGO and _env_non_modello(pezzo.lower()):
            return "file d'ambiente: %s" % pezzo
        if _rischio_jolly(pezzo):
            return "carattere jolly che puo' colpire un file di segreti: %s" % pezzo
    return None


def _elenca_ambiente(programma, args):
    if programma in ("env", _CMD_STAMPA_AMBIENTE):
        return True
    if programma == "set" and not args:
        return True
    if programma in ("export", "declare", "typeset") and all(a.startswith("-") for a in args):
        return True
    if programma == "compgen" and any(a in ("-v", "-e") for a in args):
        return True
    return False


def _segmento_segreti(seg, modo_testo, profondita):
    """Regole sui segreti per un comando semplice. Ritorna (categoria, motivo) o None."""
    parole_grezze = _parole(seg)
    parole, ingressi = _togli_redirezioni(parole_grezze)
    for dest in ingressi:
        cat = _categoria_file(dest, per_shell=True)
        if cat or _rischio_jolly(dest):
            return "segreto", "legge con una redirezione un file di segreti (%s)" % dest
    programma, i = _programma(parole)
    if not programma:
        return None
    args = parole[i + 1:]
    args_basso = [a.lower() for a in args]
    basso = seg.lower()

    # Elenco dell'ambiente.
    if _elenca_ambiente(programma, args):
        return "segreto", "il comando elenca le variabili d'ambiente (%s)" % programma

    # Variabili-segreto stampate o spedite.
    stampatori = ("echo", "printf", "print") if modo_testo else (
        "echo", "printf", "print", "curl", "wget")
    if programma in stampatori or "<<<" in seg:
        nome = _variabile_segreto(seg)
        if nome:
            return "segreto", "il comando mostra o spedisce la variabile-segreto $%s" % nome

    if modo_testo:
        # In uno script contano solo i comandi che mostrano il contenuto di un file.
        if programma in _LETTORI_SCRIPT:
            for a in args:
                motivo = _parola_sensibile(a, programma)
                if motivo:
                    return "segreto", "mostra il contenuto di un file di segreti (%s)" % motivo
        return None

    # Shell annidate ed eval: si valuta il codice che ricevono.
    if profondita < 8:
        codice = None
        if programma in _SHELL:
            for k, a in enumerate(args):
                if re.match(r"^-[a-z]*c[a-z]*$", a) and k + 1 < len(args):
                    codice = args[k + 1]
                    break
        elif programma == "eval":
            codice = " ".join(args)
        if codice:
            esito = _esamina_bash(codice, profondita + 1)
            if esito:
                return esito[0], "nel codice passato a %s: %s" % (programma, esito[1])

    # Codice in linea che tocca l'ambiente.
    if _RE_INTERPRETE.match(programma):
        inline = any(_RE_OPZIONE_INLINE.match(a) or a in ("--eval", "--print", "eval")
                     for a in args_basso)
        if inline and (_RE_TOCCA_AMBIENTE.search(basso) or _env_non_modello(basso)
                       or re.search(r"(?<![A-Za-z0-9_])ENV(?![A-Za-z0-9_])", seg)):
            return "segreto", "codice in linea (%s) che tocca l'ambiente o un file .env" % programma

    # Lettura o copia di file di segreti, con qualunque programma che non sia un puro elenco.
    if programma in _NON_LETTORI:
        return None
    if programma == "git" and args_basso and args_basso[0] in _GIT_NON_LETTORI:
        return None
    if programma == "find" and not any(a in _FIND_CHE_AGISCE for a in args_basso):
        return None
    da_controllare = list(args)
    if programma in _GREP and not any(
            a in ("-e", "-f", "--regexp", "--file") or a.startswith(("--regexp=", "--file="))
            for a in args_basso):
        for k, a in enumerate(da_controllare):
            if not a.startswith("-"):
                del da_controllare[k]
                break
    for a in da_controllare:
        motivo = _parola_sensibile(a, programma)
        if motivo:
            return "segreto", "%s legge o copia un file di segreti (%s)" % (programma, motivo)
    return None


def _esamina_righe_shell(testo, modo_testo, profondita):
    for seg in _dividi_comandi(testo):
        esito = _segmento_segreti(seg, modo_testo, profondita)
        if esito:
            return esito
    return None


# ---------------------------------------------------------------------------
# Shell: cancellazioni e operazioni distruttive
# ---------------------------------------------------------------------------
_RE_RM = re.compile(r"(?<![a-z0-9_\-.])rm(?![a-z0-9_\-.])")
_RE_OPZIONE_RM = re.compile(r"^-[a-z0-9]*[rf][a-z0-9]*$")


def _rm_distruttivo(riga):
    for m in _RE_RM.finditer(riga):
        resto = re.split(r"[;|&)`\"']", riga[m.end():], maxsplit=1)[0]
        for t in resto.split():
            if t == "--":
                break
            if _RE_OPZIONE_RM.match(t):
                return "rm ricorsivo o forzato (%s)" % t
            if t.startswith("--") and len(t) > 3 and (
                    "--recursive".startswith(t) or "--force".startswith(t)):
                return "rm ricorsivo o forzato (%s)" % t
        if re.search(r"[*?\[]|\{[^}]*,", resto):
            return "rm con caratteri jolly"
    return None


def _git_distruttivo(parole):
    programma, i = _programma(parole)
    if programma != "git":
        return None
    args = [a.lower() for a in parole[i + 1:]]
    j = 0
    while j < len(args) and args[j].startswith("-"):
        if args[j] in ("-c", "--git-dir", "--work-tree", "--namespace"):
            j += 2
        else:
            j += 1
    if j >= len(args):
        return None
    sotto, resto = args[j], args[j + 1:]
    if sotto == "clean":
        if any(r == "--dry-run" or re.match(r"^-[a-z]*n[a-z]*$", r) for r in resto):
            return None
        return "git clean"
    if sotto == "push":
        for r in resto:
            if r.startswith("--force") or re.match(r"^-[a-z]*f[a-z]*$", r) or (
                    r.startswith("+") and len(r) > 1):
                return "git push forzato (%s)" % r
        return None
    if sotto == "reset" and "--hard" in resto:
        return "git reset --hard"
    if sotto == "checkout" and ("." in resto or ":/" in resto or "-f" in resto
                                or "--force" in resto):
        return "git checkout che scarta le modifiche"
    if sotto == "restore" and ("." in resto or ":/" in resto):
        if "--staged" in resto and "--worktree" not in resto and "-w" not in resto:
            return None
        return "git restore che scarta le modifiche"
    return None


def _distruttivo(comando):
    """Motivo se il comando cancella in blocco o butta via lavoro, altrimenti None.

    Come le altre regole sul testo, lavora sul comando ridotto a una riga: `rm` a capo `-rf`
    resta una cancellazione ricorsiva.
    """
    for riga in (re.sub(r"\s+", " ", comando).strip().lower(),):
        if not riga:
            continue
        motivo = _rm_distruttivo(riga)
        if motivo:
            return motivo
        if re.search(_parola("rmdir"), riga):
            return "rmdir"
        if re.search(_parola("find") + r".*-delete", riga):
            return "find con -delete"
        if re.search(_parola("find") + r".*-(?:exec|execdir|ok|okdir)\s+(?:\S*/)?"
                     r"(?:rm|rmdir|unlink|shred)(?![a-z0-9_])", riga):
            return "find che lancia una cancellazione"
        if re.search(_parola("xargs") + r"[^|;&]*?(?:^|\s)(?:\S*/)?(?:rm|rmdir|unlink|shred)"
                     r"(?![a-z0-9_\-])", riga):
            return "cancellazione di massa con xargs"
        if re.search(r">\s*/dev/sd", riga):
            return "scrittura diretta su un disco"
        if "mkfs" in riga:
            return "formattazione di un disco (mkfs)"
        if re.search(_parola("dd") + r"[^;|&]*(?<![a-z0-9_])if=", riga):
            return "copia a basso livello con dd"
    for seg in _dividi_comandi(comando):
        motivo = _git_distruttivo(_togli_redirezioni(_parole(seg))[0])
        if motivo:
            return motivo
    return None


# ---------------------------------------------------------------------------
# Shell: regole sull'intero comando
# ---------------------------------------------------------------------------
_RE_NOMINA_RISERVATA = re.compile(r"(?<![a-z0-9])_local")
_RE_PURO_ELENCO = re.compile(r"^(?:ls|du)(?![A-Za-z0-9_])")
_CARATTERI_NON_ELENCO = set("|;&<>`$()")


def _base64_in_interprete(riga):
    return re.search(
        _parola("base64") + r"[^|]*?(?:-d|--decode)[^|]*\|\s*(?:\S*/)?"
        r"(?:sh|bash|zsh|python|python3|ruby|perl|node)(?=\s|$|[;&|)])", riga)


def _sostituzioni(testo):
    """Testi dentro $( ... ) (con parentesi bilanciate) e dentro coppie di apici inversi."""
    trovati = []
    i = 0
    while True:
        k = testo.find("$(", i)
        if k < 0:
            break
        livello, j = 1, k + 2
        while j < len(testo) and livello:
            if testo[j] == "(":
                livello += 1
            elif testo[j] == ")":
                livello -= 1
            j += 1
        trovati.append(testo[k + 2:j - 1] if livello == 0 else testo[k + 2:])
        i = k + 2
    trovati.extend(re.findall(r"`([^`]*)`", testo))
    return [t for t in trovati if t.strip()]


def _esamina_bash(comando, profondita=0):
    """Ritorna (categoria, motivo) se il comando va bloccato, altrimenti None."""
    riga = re.sub(r"\s+", " ", comando).strip()
    if not riga:
        return None
    basso = riga.lower()

    # Cartella riservata: dalla shell si elenca soltanto.
    if _RE_NOMINA_RISERVATA.search(basso):
        puro = _RE_PURO_ELENCO.match(riga) and not (set(riga) & _CARATTERI_NON_ELENCO)
        if not puro:
            return "riservata", "il comando nomina la cartella _local-only: dalla shell si puo' solo elencarla"
    if re.search(_parola("cat") + r".*_local-only", basso):
        return "riservata", "cat su un percorso della cartella _local-only"

    # Segreti.
    if re.search(_parola(_CMD_STAMPA_AMBIENTE), basso):
        return "segreto", "il comando stampa le variabili d'ambiente"
    if _base64_in_interprete(basso):
        return "segreto", "decodifica base64 passata a un interprete (comando nascosto)"
    esito = _esamina_righe_shell(comando, modo_testo=False, profondita=profondita)
    if esito:
        return esito

    # Cancellazioni e operazioni distruttive.
    motivo = _distruttivo(comando)
    if motivo:
        return "cancellazione", motivo

    # Sostituzioni di comando.
    if profondita < 8:
        for interno in _sostituzioni(riga):
            esito = _esamina_bash(interno, profondita + 1)
            if esito:
                return esito[0], "dentro una sostituzione di comando: " + esito[1]
    return None


def check_bash_command(command):
    """Ritorna il motivo (stringa non vuota) se il comando sarebbe bloccato, altrimenti None.

    Stesse regole dell'hook sullo strumento Bash. Se il controllo stesso fallisce per un
    errore interno ritorna un motivo: chi chiama (auto-approve) si astiene e decide l'utente.
    """
    if not isinstance(command, str) or not command.strip():
        return None
    try:
        esito = _esamina_bash(command)
    except Exception as e:  # noqa: BLE001 - un guasto non deve diventare un via libera
        return "errore interno nel controllo del comando (%s): comando non verificato" % (
            type(e).__name__)
    return esito[1] if esito else None


# ---------------------------------------------------------------------------
# Smistamento per strumento
# ---------------------------------------------------------------------------
def _testo(diz, chiave):
    """Valore testuale di un campo: mancante o nullo vale vuoto; altro tipo e' forma inattesa."""
    v = diz.get(chiave)
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    raise _FormaInattesa("il campo %s non e' un testo" % chiave)


def _luogo_vietato(valore, con_sensibili):
    """Controllo dei campi che dicono dove cercare (Grep e Glob)."""
    basso = valore.lower()
    if re.search(r"(?<![a-z0-9])_local(?:-only|[*?\[{])", basso):
        return "riservata", "la ricerca tocca la cartella _local-only (%s)" % valore
    if con_sensibili:
        cat = _categoria_file(valore)
        if cat:
            return "segreto", "la ricerca guarda dentro un percorso sensibile (%s: %s)" % (cat, valore)
    if _env_non_modello(basso):
        return "segreto", "la ricerca tocca file d'ambiente (%s)" % valore
    return None


def valuta(dati):
    """Ritorna (categoria, motivo) se lo strumento va bloccato, altrimenti None."""
    if not isinstance(dati, dict):
        raise _FormaInattesa("l'ingresso non e' un oggetto JSON")
    strumento = _testo(dati, "tool_name")
    ingresso = dati.get("tool_input")
    if ingresso is None:
        ingresso = {}
    if not isinstance(ingresso, dict):
        raise _FormaInattesa("tool_input non e' un oggetto")

    if strumento == "Read":
        percorso = _testo(ingresso, "file_path")
        if not percorso:
            return None
        if _call_riservata(percorso):
            return None
        cat = _categoria_file(percorso)
        if cat:
            categoria = "riservata" if "_local-only" in cat else "segreto"
            return categoria, "lettura di un file sensibile (%s: %s)" % (cat, percorso)
        return None

    if strumento == "Bash":
        comando = _testo(ingresso, "command")
        if not comando.strip():
            return None
        return _esamina_bash(comando)

    if strumento == "Grep":
        for campo in ("path", "glob"):
            valore = _testo(ingresso, campo)
            if valore:
                esito = _luogo_vietato(valore, con_sensibili=True)
                if esito:
                    return esito
        return None

    if strumento == "Glob":
        for campo in ("pattern", "path"):
            valore = _testo(ingresso, campo)
            if valore:
                esito = _luogo_vietato(valore, con_sensibili=False)
                if esito:
                    return esito
        return None

    if strumento in ("Edit", "Write"):
        percorso = _testo(ingresso, "file_path")
        if percorso:
            cat = _categoria_file(percorso)
            if cat:
                categoria = "riservata" if "_local-only" in cat else "segreto"
                return categoria, "scrittura su un file sensibile (%s: %s)" % (cat, percorso)
            if _fuori_dal_vault(percorso):
                return "fuori", "il percorso %s sta fuori dalla cartella del vault" % percorso
        testo = _testo(ingresso, "content") or _testo(ingresso, "new_string")
        if percorso and testo:
            motivo = _testo_espone(percorso, testo)
            if motivo:
                return "segreto", motivo + "; scrivere script che espongono segreti non e' permesso"
        return None

    return None


def main():
    try:
        dati = json.loads(sys.stdin.read())
    except Exception:  # noqa: BLE001 - JSON illeggibile, stdin vuoto, byte non validi
        sys.stderr.write(_messaggio("ingresso", "l'ingresso di block-secrets non e' JSON valido") + "\n")
        return 2
    try:
        esito = valuta(dati)
    except _FormaInattesa as e:
        sys.stderr.write(_messaggio("ingresso", "ingresso di block-secrets di forma inattesa: %s" % e) + "\n")
        return 2
    except Exception as e:  # noqa: BLE001 - un guasto interno non ferma ogni strumento
        sys.stderr.write("block-secrets: errore interno (%s), controllo saltato\n" % type(e).__name__)
        return 0
    if esito:
        sys.stderr.write(_messaggio(esito[0], esito[1]) + "\n")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
