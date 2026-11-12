# 2nd Brain Hero Mode · Copyright (c) 2026 Alessandro Pacifico (Pacibrand).
# Vedi LICENZA.md nella radice del vault.
"""Hook PreToolUse: protegge i documenti-ancora del vault dalla riscrittura automatica.

Le ancore sono i tre file di regole (CLAUDE.md, CAPISALDI.md, ARCHITETTURA.md), riconosciuti
per nome esatto senza distinguere maiuscole e minuscole, ovunque dentro il vault. Fuori dal
vault (la cartella in CLAUDE_PROJECT_DIR) non si applica nulla.

- Edit e Write su un'ancora: si chiede conferma all'utente (uscita 0 con JSON "ask").
- Bash: si blocca (uscita 2) solo il comando che SCRIVE, sposta o cancella un'ancora. Le
  letture passano, anche la copia altrove e il nome citato in un testo.
- ALLOW_ANCHOR_EDIT=1 lascia passare tutto.
- Ingresso illeggibile o errore imprevisto: uscita 0 con una riga su stderr.

Non scrive su disco e non usa la rete. Legge il disco solo per risolvere i percorsi
(collegamenti simbolici, cartelle di destinazione).
"""

import json
import os
import re
import sys

# Nome in minuscolo -> grafia canonica usata nei messaggi.
ANCORE = {
    "claude.md": "CLAUDE.md",
    "capisaldi.md": "CAPISALDI.md",
    "architettura.md": "ARCHITETTURA.md",
}

# Il nome di un'ancora dentro un testo libero (codice in linea, corpo di un documento in
# linea): non attaccato ad altri caratteri di nome, quindi CLAUDE.md.bak non conta.
RE_ANCORA_NEL_TESTO = re.compile(
    r"(?<![\w.\-])(claude|capisaldi|architettura)\.md(?![\w\-]|\.\w)", re.IGNORECASE
)
# Caratteri che chiudono un percorso dentro un testo libero.
DELIMITATORI_PERCORSO = set(" \t\n'\"(),;=[]{}<>`")

RE_ASSEGNAZIONE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
RE_INTERPRETE = re.compile(
    r"^(python[0-9.]*|node|nodejs|ruby|perl[0-9.]*|php|osascript|deno|bun|lua|pwsh)$"
)
SHELL = {"bash", "sh", "zsh", "dash", "ksh", "fish"}
ESTENSIONI_SCRIPT = (".sh", ".bash", ".zsh", ".py", ".rb", ".pl", ".js", ".mjs", ".ts", ".php")

# Comandi per cui un'ancora fra gli argomenti, in qualunque posizione, vuol dire scrittura.
SCRIVONO_SEMPRE = {"rm", "unlink", "truncate", "shred", "patch", "tee", "mv"}
# Comandi che scrivono solo sulla destinazione (l'ancora come sorgente è una lettura).
COPIANO = {"cp", "install", "rsync", "ln", "scp", "ditto", "mv"}
# Opzioni che prendono un valore, per comando, così il valore non passa per un percorso.
OPZIONI_CON_VALORE = {
    "cp": {"-t", "-S", "--target-directory", "--suffix"},
    "mv": {"-t", "-S", "--target-directory", "--suffix"},
    "ln": {"-t", "-S", "--target-directory", "--suffix"},
    "install": {"-t", "-m", "-o", "-g", "-S", "--target-directory", "--mode", "--owner",
                "--group", "--suffix"},
    "rsync": {"-e", "-f", "-T", "--rsh", "--exclude", "--include", "--filter",
              "--temp-dir"},
    "scp": {"-P", "-i", "-F", "-o", "-c", "-l", "-S", "-J"},
    "ditto": set(),
}

# Comandi "involucro": il comando vero viene dopo. Valore: opzioni che prendono un valore.
INVOLUCRI = {
    "sudo": {"-u", "-g", "-C", "-h", "-p", "-U"},
    "doas": {"-u"},
    "env": {"-u", "-C", "-S"},
    "command": set(),
    "builtin": set(),
    "exec": {"-a"},
    "nohup": set(),
    "nice": {"-n"},
    "time": set(),
    "timeout": {"-s", "-k", "--signal", "--kill-after"},
    "stdbuf": {"-i", "-o", "-e"},
    "caffeinate": {"-t", "-w"},
    "xargs": {"-I", "-n", "-P", "-L", "-d", "-E", "-s", "-a"},
    "{": set(),
    "!": set(),
    "then": set(),
    "do": set(),
    "else": set(),
    "elif": set(),
    "if": set(),
    "while": set(),
    "until": set(),
}


# ---------------------------------------------------------------------------
# Scomposizione del comando di shell
# ---------------------------------------------------------------------------

class Parola:
    """Una parola del comando, già senza apici. `espansa` = contiene $ o apici inversi."""

    __slots__ = ("testo", "espansa", "pos")

    def __init__(self, testo, espansa=False, pos=0):
        self.testo = testo
        self.espansa = espansa
        self.pos = pos


class Comando:
    """Un comando semplice: parole, redirezioni e corpi dei documenti in linea."""

    __slots__ = ("parole", "redirezioni", "corpi")

    def __init__(self):
        self.parole = []
        self.redirezioni = []  # coppie (operatore, Parola); "leggi" per quelle in ingresso
        self.corpi = []        # testo dei documenti in linea (<<EOF)

    def vuoto(self):
        return not (self.parole or self.redirezioni or self.corpi)


def _fine_doppie(s, i):
    """Da dopo un apice doppio aperto, ritorna l'indice subito dopo quello che lo chiude."""
    n = len(s)
    while i < n:
        c = s[i]
        if c == "\\":
            i += 2
            continue
        if c == '"':
            return i + 1
        i += 1
    return n


def _fine_parentesi(s, i):
    """Da dopo una parentesi aperta, ritorna l'indice della parentesi che la chiude."""
    profondita = 1
    n = len(s)
    while i < n:
        c = s[i]
        if c == "\\":
            i += 2
            continue
        if c == "'":
            k = s.find("'", i + 1)
            i = n if k < 0 else k + 1
            continue
        if c == '"':
            i = _fine_doppie(s, i + 1)
            continue
        if c == "(":
            profondita += 1
        elif c == ")":
            profondita -= 1
            if profondita == 0:
                return i
        i += 1
    return n


def _fine_apice_inverso(s, i):
    """Da dopo un apice inverso aperto, ritorna l'indice di quello che lo chiude."""
    n = len(s)
    while i < n:
        if s[i] == "\\":
            i += 2
            continue
        if s[i] == "`":
            return i
        i += 1
    return n


class _Scompositore:
    """Spezza un comando di shell in comandi semplici.

    Separano i comandi: a capo, `;`, `&`, `&&`, `|`, `||`, `|&` e le parentesi tonde. Le
    sostituzioni di comando `$( )`, gli apici inversi e le sostituzioni di processo `<( )`
    vengono scomposte a loro volta e i loro comandi entrano nell'elenco.
    """

    def __init__(self, s, profondita):
        self.s = s
        self.profondita = profondita
        self.comandi = []
        self.corrente = Comando()
        self.buf = []
        self.in_parola = False
        self.espansa = False
        self.inizio = 0
        self.attesa = None           # redirezione in attesa del bersaglio
        self.attesa_heredoc = None   # True/False: la prossima parola è un delimitatore
        self.heredoc = []            # (delimitatore, togli_tab, comando a cui appartiene)

    # -- parole e comandi --------------------------------------------------

    def _apri(self, i):
        if not self.in_parola:
            self.in_parola = True
            self.inizio = i

    def chiudi_parola(self):
        if not self.in_parola:
            return
        p = Parola("".join(self.buf), self.espansa, self.inizio)
        if self.attesa_heredoc is not None:
            self.heredoc.append((p.testo, self.attesa_heredoc, self.corrente))
            self.attesa_heredoc = None
        elif self.attesa is not None:
            self.corrente.redirezioni.append((self.attesa, p))
            self.attesa = None
        else:
            self.corrente.parole.append(p)
        self.buf = []
        self.in_parola = False
        self.espansa = False

    def chiudi_comando(self):
        self.chiudi_parola()
        self.attesa = None
        if not self.corrente.vuoto():
            self.comandi.append(self.corrente)
        self.corrente = Comando()

    def annida(self, testo):
        if self.profondita < 8:
            self.comandi.extend(scomponi(testo, self.profondita + 1))

    def salta_heredoc(self, i):
        """Dopo l'a capo: legge i corpi dei documenti in linea in attesa."""
        s = self.s
        n = len(s)
        for delim, togli_tab, comando in self.heredoc:
            righe = []
            while i < n:
                k = s.find("\n", i)
                fine = n if k < 0 else k
                riga = s[i:fine]
                i = fine + 1
                confronto = riga.lstrip("\t") if togli_tab else riga
                if confronto == delim:
                    break
                righe.append(riga)
            comando.corpi.append("\n".join(righe))
            if comando not in self.comandi and not comando.vuoto():
                self.comandi.append(comando)
        self.heredoc = []
        return min(i, n)

    def _togli_descrittore(self):
        """Prima di > o <: una parola fatta solo di cifre è il numero del descrittore."""
        if self.in_parola and self.buf and "".join(self.buf).isdigit() and not self.espansa:
            self.buf = []
            self.in_parola = False
        else:
            self.chiudi_parola()

    # -- ciclo principale --------------------------------------------------

    def esegui(self):
        s = self.s
        n = len(s)
        i = 0
        while i < n:
            c = s[i]
            if c in " \t\r":
                self.chiudi_parola()
                i += 1
            elif c == "\n" and self.attesa is not None and not self.in_parola:
                # Redirezione rimasta a metà riga: il bersaglio sulla riga dopo conta lo stesso.
                i += 1
            elif c == "\n":
                self.chiudi_comando()
                i += 1
                if self.heredoc:
                    i = self.salta_heredoc(i)
            elif c == "#" and not self.in_parola:
                k = s.find("\n", i)
                i = n if k < 0 else k
            elif c == "\\":
                if i + 1 < n and s[i + 1] == "\n":
                    i += 2
                elif i + 1 < n:
                    self._apri(i)
                    self.buf.append(s[i + 1])
                    i += 2
                else:
                    i += 1
            elif c == "'":
                self._apri(i)
                k = s.find("'", i + 1)
                if k < 0:
                    k = n
                self.buf.append(s[i + 1:k])
                i = k + 1
            elif c == '"':
                self._apri(i)
                i = self._doppie(i + 1)
            elif c == "`":
                self._apri(i)
                k = _fine_apice_inverso(s, i + 1)
                self.annida(s[i + 1:k])
                self.buf.append(s[i:k + 1])
                self.espansa = True
                i = k + 1
            elif c == "$" and s[i + 1:i + 2] == "(":
                self._apri(i)
                k = _fine_parentesi(s, i + 2)
                self.annida(s[i + 2:k])
                self.buf.append(s[i:k + 1])
                self.espansa = True
                i = k + 1
            elif c == "$":
                self._apri(i)
                self.buf.append(c)
                self.espansa = True
                i += 1
            elif c in "<>" and s[i + 1:i + 2] == "(" and not self.in_parola:
                # Sostituzione di processo: una parola il cui contenuto è un comando.
                self._apri(i)
                k = _fine_parentesi(s, i + 2)
                self.annida(s[i + 2:k])
                self.buf.append(s[i:k + 1])
                self.espansa = True
                i = k + 1
            elif c in "()":
                self.chiudi_comando()
                i += 1
            elif c == ";":
                self.chiudi_comando()
                i += 1
            elif c == "|":
                self.chiudi_comando()
                i += 2 if s[i + 1:i + 2] in ("|", "&") else 1
            elif c == "&":
                if s[i + 1:i + 2] == ">":
                    self.chiudi_parola()
                    op = "&>>" if s[i + 2:i + 3] == ">" else "&>"
                    self.attesa = op
                    i += len(op)
                else:
                    self.chiudi_comando()
                    i += 2 if s[i + 1:i + 2] == "&" else 1
            elif c == ">":
                self._togli_descrittore()
                nxt = s[i + 1:i + 2]
                if nxt == ">":
                    op, i = ">>", i + 2
                elif nxt == "|":
                    op, i = ">|", i + 2
                elif nxt == "&":
                    m = re.match(r"[ \t]*(\d+|-)(?=[\s;|&)]|$)", s[i + 2:])
                    if m:
                        # Duplicazione di descrittore (2>&1): nessun file.
                        i = i + 2 + m.end()
                        continue
                    op, i = ">&", i + 2
                else:
                    op, i = ">", i + 1
                self.attesa = op
            elif c == "<":
                self._togli_descrittore()
                if s.startswith("<<<", i):
                    self.attesa, i = "leggi", i + 3
                elif s.startswith("<<", i):
                    togli = s[i + 2:i + 3] == "-"
                    self.attesa_heredoc = togli
                    i += 3 if togli else 2
                elif s[i + 1:i + 2] == ">":
                    # <> apre il file anche in scrittura.
                    self.attesa, i = "<>", i + 2
                elif s[i + 1:i + 2] == "&":
                    self.attesa, i = "leggi", i + 2
                else:
                    self.attesa, i = "leggi", i + 1
            else:
                self._apri(i)
                self.buf.append(c)
                i += 1
        self.chiudi_comando()
        if self.heredoc:
            self.salta_heredoc(n)
        return self.comandi

    def _doppie(self, i):
        """Contenuto fra apici doppi: toglie gli apici, segue $( ) e apici inversi."""
        s = self.s
        n = len(s)
        while i < n:
            c = s[i]
            if c == "\\" and i + 1 < n:
                if s[i + 1] in '"\\$`':
                    self.buf.append(s[i + 1])
                else:
                    self.buf.append(s[i:i + 2])
                i += 2
            elif c == '"':
                return i + 1
            elif c == "$" and s[i + 1:i + 2] == "(":
                k = _fine_parentesi(s, i + 2)
                self.annida(s[i + 2:k])
                self.buf.append(s[i:k + 1])
                self.espansa = True
                i = k + 1
            elif c == "`":
                k = _fine_apice_inverso(s, i + 1)
                self.annida(s[i + 1:k])
                self.buf.append(s[i:k + 1])
                self.espansa = True
                i = k + 1
            else:
                if c == "$":
                    self.espansa = True
                self.buf.append(c)
                i += 1
        return n


def scomponi(s, profondita=0):
    """Ritorna l'elenco dei comandi semplici contenuti nel testo di shell `s`."""
    return _Scompositore(s, profondita).esegui()


# ---------------------------------------------------------------------------
# Percorsi e vault
# ---------------------------------------------------------------------------

class Contesto:
    """Cartella di lavoro corrente (None se non si può sapere) e radice del vault."""

    def __init__(self, base, vault):
        self.base = base
        self.vault = vault


def _dentro(percorso, vault):
    reale = os.path.realpath(percorso)
    return reale == vault or reale.startswith(vault.rstrip(os.sep) + os.sep)


def _canonica(nome):
    return ANCORE.get(nome.lower())


def _percorso_ancora(testo, espansa, ctx):
    """Se `testo` è un percorso che porta a un'ancora dentro il vault, ritorna il nome canonico."""
    if not testo:
        return None
    canon = _canonica(testo.rsplit("/", 1)[-1])
    if not canon:
        return None
    if ctx.vault is None:
        return canon  # vault ignoto: prudenza, vale ovunque
    percorso = os.path.expanduser(testo)
    if espansa or "$" in percorso:
        return canon  # percorso non risolvibile: prudenza
    if not os.path.isabs(percorso):
        if ctx.base is None:
            return canon
        percorso = os.path.join(ctx.base, percorso)
    return canon if _dentro(percorso, ctx.vault) else None


def _ancora_parola(p, ctx):
    return _percorso_ancora(p.testo, p.espansa, ctx)


def _ancora_ovunque(p, ctx):
    """Come _ancora_parola, ma cerca il nome anche dentro un testo libero (codice in linea)."""
    if _canonica(p.testo.rsplit("/", 1)[-1]):
        return _ancora_parola(p, ctx)
    return _ancora_nel_testo(p.testo, ctx)


def _ancora_nel_testo(testo, ctx):
    for m in RE_ANCORA_NEL_TESTO.finditer(testo):
        sinistra = m.start()
        while sinistra > 0 and testo[sinistra - 1] not in DELIMITATORI_PERCORSO:
            sinistra -= 1
        canon = _percorso_ancora(testo[sinistra:m.end()], False, ctx)
        if canon:
            return canon
    return None


def _risolvi_cartella(testo, espansa, ctx):
    """Nuova cartella di lavoro dopo un `cd` (None se non si può sapere)."""
    if espansa or "$" in testo or testo == "-":
        return None
    t = os.path.expanduser(testo)
    if os.path.isabs(t):
        return os.path.normpath(t)
    if ctx.base is None:
        return None
    return os.path.normpath(os.path.join(ctx.base, t))


# ---------------------------------------------------------------------------
# Regole per comando
# ---------------------------------------------------------------------------

def _opzione_corta(t):
    return t.startswith("-") and not t.startswith("--") and len(t) > 1


def _remoto(t):
    """host:percorso (scp, rsync): la destinazione non è locale."""
    return re.match(r"^[^/]*:", t) is not None


def _copia(nome, args, ctx):
    """cp, mv, ln, install, rsync, scp, ditto: si guarda dove si scrive."""
    valori = OPZIONI_CON_VALORE.get(nome, set())
    posizionali = []
    cartella = None
    i = 0
    fine_opzioni = False
    while i < len(args):
        p = args[i]
        t = p.testo
        i += 1
        if not fine_opzioni and t == "--":
            fine_opzioni = True
            continue
        if not fine_opzioni and t.startswith("-") and t != "-":
            if t in ("-t", "--target-directory"):
                if i < len(args):
                    cartella = args[i]
                    i += 1
            elif t.startswith("--target-directory="):
                cartella = Parola(t.split("=", 1)[1], p.espansa, p.pos)
            elif t.startswith("-t") and nome in ("cp", "mv", "ln", "install") and len(t) > 2:
                cartella = Parola(t[2:], p.espansa, p.pos)
            elif t in valori:
                i += 1
            continue
        posizionali.append(p)
    if cartella is not None:
        destinazione, sorgenti = cartella, posizionali
        e_cartella = True
    elif len(posizionali) >= 2:
        destinazione, sorgenti = posizionali[-1], posizionali[:-1]
        e_cartella = False
    elif nome == "ln" and len(posizionali) == 1:
        destinazione, sorgenti = Parola(".", False, posizionali[0].pos), posizionali
        e_cartella = True
    else:
        return None
    if nome in ("scp", "rsync") and _remoto(destinazione.testo):
        return None
    if not e_cartella:
        canon = _ancora_parola(destinazione, ctx)
        if canon:
            return canon, destinazione
        t = destinazione.testo
        e_cartella = t.endswith("/") or t in (".", "..") or _e_cartella(t, destinazione, ctx)
    if e_cartella:
        for s in sorgenti:
            nome_file = s.testo.rstrip("/").rsplit("/", 1)[-1]
            if not _canonica(nome_file):
                continue
            candidato = os.path.join(destinazione.testo, nome_file)
            canon = _percorso_ancora(candidato, destinazione.espansa or s.espansa, ctx)
            if canon:
                return canon, destinazione
    return None


def _e_cartella(t, p, ctx):
    if p.espansa or "$" in t:
        return False
    t = os.path.expanduser(t)
    if not os.path.isabs(t):
        if ctx.base is None:
            return False
        t = os.path.join(ctx.base, t)
    return os.path.isdir(t)


def _prima(args, ctx, funzione=_ancora_parola):
    for p in args:
        canon = funzione(p, ctx)
        if canon:
            return canon, p
    return None


def _valore_opzione(args, lunghe, lettera):
    """Valori di un'opzione: -X val, -Xval, cluster che finisce con X, --lunga val, --lunga=val."""
    trovati = []
    i = 0
    while i < len(args):
        p = args[i]
        t = p.testo
        i += 1
        valore = None
        if t in lunghe:
            if i < len(args):
                valore = args[i]
                i += 1
        elif any(t.startswith(lu + "=") for lu in lunghe):
            valore = Parola(t.split("=", 1)[1], p.espansa, p.pos)
        elif _opzione_corta(t) and lettera in t[1:]:
            resto = t[t.index(lettera, 1) + 1:]
            if resto:
                valore = Parola(resto, p.espansa, p.pos)
            elif i < len(args):
                valore = args[i]
                i += 1
        if valore is not None:
            trovati.append(valore)
    return trovati


def _curl(args, ctx):
    for v in _valore_opzione(args, ("--output", "-o"), "o"):
        canon = _ancora_parola(v, ctx)
        if canon:
            return canon, v
    nome_remoto = any(
        t in ("-O", "--remote-name", "--remote-name-all") or (_opzione_corta(t) and "O" in t[1:])
        for t in (p.testo for p in args)
    )
    if nome_remoto:
        for p in args:
            t = p.testo
            if t.startswith("-") or "://" not in t:
                continue
            nome_file = t.split("?", 1)[0].split("#", 1)[0].rstrip("/").rsplit("/", 1)[-1]
            canon = _percorso_ancora(nome_file, p.espansa, ctx)
            if canon:
                return canon, p
    return None


def _wget(args, ctx):
    for v in _valore_opzione(args, ("--output-document", "-O"), "O"):
        canon = _ancora_parola(v, ctx)
        if canon:
            return canon, v
    return None


def _sul_posto_sed(args):
    for p in args:
        t = p.testo
        if t == "--in-place" or t.startswith("--in-place="):
            return True
        if _opzione_corta(t) and "i" in t[1:]:
            return True
    return False


def _sul_posto_awk(args):
    for i, p in enumerate(args):
        t = p.testo
        if t in ("-iinplace", "--include=inplace"):
            return True
        if t in ("-i", "--include") and i + 1 < len(args) and \
                args[i + 1].testo in ("inplace", "inplace.awk"):
            return True
    return False


def _non_opzioni(args):
    return [p for p in args if not p.testo.startswith("-")]


def _git(args, ctx):
    j = 0
    sotto_ctx = ctx
    while j < len(args) and args[j].testo.startswith("-"):
        o = args[j].testo
        j += 1
        if o == "-C" and j < len(args):
            sotto_ctx = Contesto(_risolvi_cartella(args[j].testo, args[j].espansa, ctx),
                                 ctx.vault)
            j += 1
        elif o in ("-c", "--git-dir", "--work-tree", "--namespace") and j < len(args):
            j += 1
    if j >= len(args):
        return None
    sotto = args[j].testo
    resto = args[j + 1:]
    if sotto in ("rm", "mv", "checkout"):
        return _prima(_non_opzioni(resto), sotto_ctx)
    if sotto == "restore":
        testi = [p.testo for p in resto]
        indice = any(t in ("--staged", "-S") or (_opzione_corta(t) and "S" in t[1:])
                     for t in testi)
        lavoro = any(t in ("--worktree", "-W") or (_opzione_corta(t) and "W" in t[1:])
                     for t in testi)
        if indice and not lavoro:
            return None  # tocca solo l'indice, non il file
        return _prima(_non_opzioni(resto), sotto_ctx)
    return None


def _find(args, ctx):
    testi = [p.testo for p in args]
    scrive = "-delete" in testi
    for k, t in enumerate(testi):
        if t in ("-exec", "-execdir", "-ok", "-okdir") and k + 1 < len(testi):
            interno = testi[k + 1].rsplit("/", 1)[-1]
            fine = k + 2
            while fine < len(testi) and testi[fine] not in (";", "+"):
                fine += 1
            sotto = args[k + 2:fine]
            if interno in SCRIVONO_SEMPRE or RE_INTERPRETE.match(interno) or interno in SHELL:
                scrive = True
            elif interno in ("sed", "ex") and _sul_posto_sed(sotto):
                scrive = True
            elif interno in ("awk", "gawk") and _sul_posto_awk(sotto):
                scrive = True
    if not scrive:
        return None
    return _prima(args, ctx, _ancora_ovunque)


def _shell(args, ctx):
    for k, p in enumerate(args):
        t = p.testo
        if _opzione_corta(t) and "c" in t[1:]:
            if k + 1 < len(args):
                for comando in scomponi(args[k + 1].testo, 1):
                    trovata = _esamina(comando, Contesto(ctx.base, ctx.vault))
                    if trovata:
                        return trovata
                # Argomenti dopo il codice ($0, $1, ...): lo script li riceve, prudenza.
                return _prima(args[k + 2:], ctx, _ancora_ovunque)
            return None
    return _prima(args, ctx, _ancora_ovunque)


def _esamina(comando, ctx):
    """Ritorna (nome canonico, Parola) della prima ancora scritta dal comando, o None."""
    colpi = []
    for op, p in comando.redirezioni:
        if op == "leggi":
            continue
        # Un bersaglio calcolato ($VAR, `...`) che nomina un'ancora vale come ancora.
        canon = _ancora_ovunque(p, ctx) if p.espansa else _ancora_parola(p, ctx)
        if canon:
            colpi.append((canon, p))

    parole = comando.parole
    i = 0
    while i < len(parole):
        t = parole[i].testo
        if RE_ASSEGNAZIONE.match(t):
            i += 1
            continue
        nome = t.rsplit("/", 1)[-1]
        if nome in INVOLUCRI:
            valori = INVOLUCRI[nome]
            i += 1
            while i < len(parole) and parole[i].testo.startswith("-") and parole[i].testo != "-":
                o = parole[i].testo
                i += 1
                if o == "--":
                    break
                if o in valori:
                    i += 1
            while nome == "env" and i < len(parole) and RE_ASSEGNAZIONE.match(parole[i].testo):
                i += 1
            if nome == "timeout" and i < len(parole):
                i += 1  # la durata
            continue
        break

    risultato = None
    if i < len(parole):
        nome = parole[i].testo.rsplit("/", 1)[-1]
        args = parole[i + 1:]
        if nome in ("cd", "pushd"):
            destinazioni = [p for p in args if not p.testo.startswith("-")]
            if destinazioni:
                ctx.base = _risolvi_cartella(destinazioni[0].testo, destinazioni[0].espansa, ctx)
            else:
                ctx.base = os.path.expanduser("~")
        elif nome in SCRIVONO_SEMPRE and nome != "mv":
            risultato = _prima(args, ctx)
        elif nome == "mv":
            risultato = _prima(_non_opzioni(args), ctx) or _copia(nome, args, ctx)
        elif nome in COPIANO:
            risultato = _copia(nome, args, ctx)
        elif nome == "dd":
            for p in args:
                if p.testo.startswith("of="):
                    q = Parola(p.testo[3:], p.espansa, p.pos)
                    canon = _ancora_parola(q, ctx)
                    if canon:
                        risultato = (canon, q)
                        break
        elif nome == "curl":
            risultato = _curl(args, ctx)
        elif nome == "wget":
            risultato = _wget(args, ctx)
        elif nome in ("sed", "ex"):
            if _sul_posto_sed(args):
                risultato = _prima(args, ctx)
        elif nome in ("awk", "gawk"):
            if _sul_posto_awk(args):
                risultato = _prima(args, ctx)
        elif nome == "git":
            risultato = _git(args, ctx)
        elif nome == "find":
            risultato = _find(args, ctx)
        elif nome in SHELL:
            risultato = _shell(args, ctx)
            if not risultato:
                for corpo in comando.corpi:
                    for interno in scomponi(corpo, 1):
                        risultato = _esamina(interno, Contesto(ctx.base, ctx.vault))
                        if risultato:
                            break
                    if risultato:
                        break
        elif RE_INTERPRETE.match(nome) or nome.endswith(ESTENSIONI_SCRIPT):
            # Interprete o script con un'ancora fra gli argomenti: non si può sapere se la
            # scrive, quindi si blocca. Vale anche per il codice passato in un documento in
            # linea (python3 - <<EOF).
            risultato = _prima(args, ctx, _ancora_ovunque)
            if not risultato and RE_INTERPRETE.match(nome):
                for corpo in comando.corpi:
                    canon = _ancora_nel_testo(corpo, ctx)
                    if canon:
                        risultato = (canon, Parola(canon, False, parole[i].pos))
                        break
    if risultato:
        colpi.append(risultato)
    if not colpi:
        return None
    return min(colpi, key=lambda c: c[1].pos)


def analizza_bash(comando, ctx):
    """Ritorna (nome canonico, testo come scritto) della prima ancora scritta, o None."""
    for semplice in scomponi(comando):
        trovata = _esamina(semplice, ctx)
        if trovata:
            return trovata[0], trovata[1].testo
    return None


# ---------------------------------------------------------------------------
# Messaggi ed esiti
# ---------------------------------------------------------------------------

def _scrivi_stderr(testo):
    try:
        sys.stderr.buffer.write((testo + "\n").encode("utf-8"))
        sys.stderr.flush()
    except Exception:
        pass


def _chiedi_conferma(canon, percorso):
    motivo = (
        "«{p}» è {c}, un documento-ancora del vault: schema statico che l'agente non "
        "riscrive di sua iniziativa. Se la modifica è voluta, basta confermare: il rischio è "
        "contenuto, perché la differenza resta visibile prima del sì e git permette di "
        "tornare indietro. Decisioni e stato non vanno qui: vanno nel MEMORY.md del "
        "progetto o in 02-memoria/."
    ).format(p=percorso, c=canon)
    uscita = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": motivo,
        }
    }
    sys.stdout.write(json.dumps(uscita))
    sys.stdout.flush()
    return 0


def _blocca(canon, scritto):
    _scrivi_stderr(
        "BLOCCO DI SICUREZZA (protect-anchors): il comando scrive, sposta o cancella "
        "«{s}», cioè {c}, un documento-ancora del vault. Da shell la scrittura sulle ancore "
        "non si conferma, si blocca; la lettura invece passa. Se la modifica è voluta: "
        "1) falla con lo strumento Edit e conferma la richiesta; 2) oppure l'utente rilancia "
        "Claude Code con ALLOW_ANCHOR_EDIT=1; 3) oppure l'utente la fa a mano. Decisioni e "
        "stato non vanno nelle ancore: vanno nel MEMORY.md del progetto o in 02-memoria/."
        .format(s=scritto, c=canon)
    )
    return 2


def _vault():
    radice = os.environ.get("CLAUDE_PROJECT_DIR") or ""
    if not radice:
        return None
    return os.path.realpath(radice)


def decidi(dati):
    """Applica le regole a un ingresso già letto. Ritorna il codice di uscita."""
    if not isinstance(dati, dict):
        return 0
    strumento = dati.get("tool_name")
    ingresso = dati.get("tool_input")
    if not isinstance(ingresso, dict):
        ingresso = {}  # tool_input nullo o di forma inattesa: vale come vuoto
    vault = _vault()
    cwd = dati.get("cwd")
    if isinstance(cwd, str) and os.path.isabs(cwd):
        base = cwd
    else:
        base = vault or os.getcwd()
    ctx = Contesto(base, vault)

    if strumento in ("Edit", "Write"):
        percorso = ingresso.get("file_path")
        if not isinstance(percorso, str) or not percorso:
            return 0
        canon = _percorso_ancora(percorso, False, ctx)
        if canon:
            return _chiedi_conferma(canon, percorso)
        return 0

    if strumento == "Bash":
        comando = ingresso.get("command")
        if not isinstance(comando, str) or not comando:
            return 0
        trovata = analizza_bash(comando, ctx)
        if trovata:
            return _blocca(*trovata)
        return 0

    return 0  # Read, Grep, Glob e ogni altro strumento: leggere le ancore è libero


def main():
    if os.environ.get("ALLOW_ANCHOR_EDIT") == "1":
        return 0  # scappatoia voluta: non si legge nemmeno l'ingresso
    try:
        grezzo = sys.stdin.buffer.read()
        dati = json.loads(grezzo.decode("utf-8", "replace"))
    except Exception:
        _scrivi_stderr("protect-anchors: ingresso illeggibile (non è JSON), nessun controllo.")
        return 0
    try:
        return decidi(dati)
    except Exception as errore:
        _scrivi_stderr("protect-anchors: errore interno ({}), nessun controllo."
                       .format(type(errore).__name__))
        return 0


if __name__ == "__main__":
    sys.exit(main())
