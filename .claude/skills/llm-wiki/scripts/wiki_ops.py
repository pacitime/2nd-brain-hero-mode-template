# 2nd Brain Hero Mode · Copyright (c) 2026 Alessandro Pacifico (Pacibrand).
# Vedi LICENZA.md nella radice del vault.
"""Controlli deterministici, in sola lettura, su un wiki piatto del vault.

Tre comandi:
  stats     conta le pagine per tipo, le fonti grezze e l'ultimo ingest
  lint      cerca collegamenti rotti, intestazioni mancanti o incomplete,
            pagine orfane e fonti grezze senza pagina di sintesi
  validate  controlla una sola pagina (intestazione e collegamenti)

Lo strumento non scrive mai nessun file. I resoconti vanno su standard output,
gli errori (d'uso e dello strumento) su standard error.
"""

import argparse
import datetime
import os
import re
import sys

# File che stanno nel wiki ma non sono pagine.
FILE_DI_SERVIZIO = ("index.md", "log.md", "SCHEMA.md")
# Voci obbligatorie dell'intestazione, gia' in ordine alfabetico.
VOCI_OBBLIGATORIE = ("created", "title", "type", "updated")
# Pagina che non e' mai orfana: e' il punto d'ingresso del wiki.
PAGINA_RADICE = "overview"
# Cartelle del vault che non si guardano quando si cercano le note esterne.
CARTELLE_ESCLUSE_VAULT = {"_local-only", "node_modules", "__pycache__"}
# Indizi che segnano la radice del vault, cercati risalendo dalla cartella del wiki.
MARCATORI_VAULT = ("CLAUDE.md", ".git")

RE_COLLEGAMENTO = re.compile(r"\[\[([^\[\]]*?)\]\]")
RE_INGEST = re.compile(r"^##\s+\[(\d{4}-\d{2}-\d{2})\]\s+ingest\b")


# ---------------------------------------------------------------- lettura

def leggi_testo(percorso):
    """Legge un file come UTF-8. Un file non decodificabile ferma tutto (scelta della specifica)."""
    with open(percorso, "r", encoding="utf-8") as f:
        return f.read()


def elenca_pagine(cartella_wiki):
    """Nomi dei file .md direttamente nel wiki, esclusi i file di servizio, in ordine alfabetico."""
    nomi = []
    for nome in os.listdir(cartella_wiki):
        if not nome.endswith(".md") or nome in FILE_DI_SERVIZIO:
            continue
        if os.path.isfile(os.path.join(cartella_wiki, nome)):
            nomi.append(nome)
    return sorted(nomi)


def leggi_intestazione(testo):
    """Restituisce il dizionario delle voci, oppure None se l'intestazione manca o e' vuota.

    Lettura volutamente semplice, non YAML: la prima riga deve essere '---', il blocco
    finisce alla prima riga successiva che comincia con '---'; ogni riga con i due punti
    da' una voce (nome prima dei primi due punti, valore dopo, senza spazi agli estremi).
    """
    righe = testo.split("\n")
    if not righe or righe[0].rstrip("\r").rstrip() != "---":
        return None
    voci = {}
    chiuso = False
    for riga in righe[1:]:
        riga = riga.rstrip("\r")
        if riga.startswith("---"):
            chiuso = True
            break
        if ":" not in riga:
            continue
        nome, valore = riga.split(":", 1)
        nome = nome.strip()
        if nome:
            voci[nome] = valore.strip()
    if not chiuso or not voci:
        return None
    return voci


def estrai_bersagli(testo):
    """Bersagli dei collegamenti [[...]] nell'ordine in cui compaiono.

    Il bersaglio e' la parte prima della barra verticale (e prima di un eventuale '#sezione'),
    senza spazi agli estremi. Un bersaglio vuoto (es. [[#sezione]]) indica la pagina stessa
    e viene restituito come stringa vuota.
    """
    bersagli = []
    for corpo in RE_COLLEGAMENTO.findall(testo):
        bersaglio = corpo.split("|", 1)[0]
        # Nelle tabelle Obsidian la barra si scrive '\|': la barra rovesciata non fa parte del nome.
        bersaglio = bersaglio.rstrip().rstrip("\\")
        bersaglio = bersaglio.split("#", 1)[0].strip()
        bersagli.append(bersaglio)
    return bersagli


# ------------------------------------------------------- note esterne al wiki

def trova_radice_vault(cartella_wiki):
    """Risale dalla cartella del wiki fino alla prima che contiene CLAUDE.md o .git."""
    corrente = os.path.realpath(cartella_wiki)
    while True:
        for marcatore in MARCATORI_VAULT:
            if os.path.exists(os.path.join(corrente, marcatore)):
                return corrente
        genitore = os.path.dirname(corrente)
        if genitore == corrente:
            return None
        corrente = genitore


class IndiceVault:
    """Elenco dei nomi di file del vault fuori dal wiki, costruito solo se serve."""

    def __init__(self, cartella_wiki):
        self._wiki = os.path.realpath(cartella_wiki)
        self._radice = trova_radice_vault(cartella_wiki)
        self._nomi = None      # nomi senza .md e nomi completi dei file
        self._percorsi = None  # percorsi relativi alla radice, con e senza .md

    def _costruisci(self):
        self._nomi = set()
        self._percorsi = set()
        if self._radice is None:
            return
        for cartella, sottocartelle, file in os.walk(self._radice):
            reale = os.path.realpath(cartella)
            if reale == self._wiki or reale.startswith(self._wiki + os.sep):
                sottocartelle[:] = []
                continue
            sottocartelle[:] = [
                s for s in sottocartelle
                if not s.startswith(".") and s not in CARTELLE_ESCLUSE_VAULT
                and os.path.realpath(os.path.join(cartella, s)) != self._wiki
            ]
            relativa = os.path.relpath(cartella, self._radice)
            for nome in file:
                if nome.startswith("."):
                    continue
                rel = nome if relativa == "." else os.path.join(relativa, nome).replace(os.sep, "/")
                self._nomi.add(nome)
                self._percorsi.add(rel)
                if nome.endswith(".md"):
                    self._nomi.add(nome[:-3])
                    self._percorsi.add(rel[:-3])

    def esiste(self, bersaglio):
        """Vero se il bersaglio indica una nota (o un file) del vault fuori dal wiki."""
        if not bersaglio:
            return False
        if self._nomi is None:
            self._costruisci()
        if "/" not in bersaglio:
            return bersaglio in self._nomi
        bersaglio = bersaglio.lstrip("/")
        if bersaglio in self._percorsi:
            return True
        suffisso = "/" + bersaglio
        return any(p.endswith(suffisso) for p in self._percorsi)


# --------------------------------------------------------------- il wiki

class Wiki:
    """Pagine del wiki gia' lette: testo, intestazione e collegamenti di ciascuna."""

    def __init__(self, cartella):
        self.cartella = cartella
        self.file_pagine = elenca_pagine(cartella)
        self.nomi = {f[:-3] for f in self.file_pagine}
        self.intestazioni = {}
        self.collegamenti = {}
        for nome_file in self.file_pagine:
            testo = leggi_testo(os.path.join(cartella, nome_file))
            self.intestazioni[nome_file] = leggi_intestazione(testo)
            self.collegamenti[nome_file] = estrai_bersagli(testo)
        self.vault = IndiceVault(cartella)

    def classifica(self, bersaglio, nome_file_corrente):
        """'valido', 'esterno' o 'rotto' per un bersaglio scritto nella pagina indicata."""
        if bersaglio == "" or bersaglio in self.nomi:
            return "valido"
        if self.vault.esiste(bersaglio):
            return "esterno"
        return "rotto"


def problemi_intestazione(voci):
    """None se l'intestazione e' a posto; 'mancante'; oppure la lista delle voci mancanti."""
    if voci is None:
        return "mancante"
    mancanti = [v for v in VOCI_OBBLIGATORIE if v not in voci]
    return mancanti or None


def risolvi_cartelle_fonti(cartella_wiki, cartelle_date):
    """Coppie (percorso da mostrare, percorso reale) delle cartelle di fonti.

    Senza --raw-dir si usa la sottocartella 'raw' del wiki. I percorsi relativi si
    risolvono rispetto alla cartella del wiki (decisione della riscrittura).
    """
    if not cartelle_date:
        cartelle_date = ["raw"]
    risultato = []
    for c in cartelle_date:
        reale = c if os.path.isabs(c) else os.path.normpath(os.path.join(cartella_wiki, c))
        risultato.append(reale)
    return risultato


def fonti_in(cartella):
    """Nomi dei file .md direttamente nella cartella, in ordine alfabetico ([] se non esiste)."""
    if not os.path.isdir(cartella):
        return []
    return sorted(
        n for n in os.listdir(cartella)
        if n.endswith(".md") and os.path.isfile(os.path.join(cartella, n))
    )


def ultimo_ingest(cartella_wiki):
    """Data piu' recente fra le righe di ingest del registro, in qualunque ordine siano scritte.

    Le date si confrontano come date; una data impossibile (es. 2030-13-45) si ignora.
    Restituisce 'nessuno' se non c'e' alcun ingest valido, None se log.md manca.
    """
    percorso = os.path.join(cartella_wiki, "log.md")
    if not os.path.isfile(percorso):
        return None
    piu_recente = None
    for riga in leggi_testo(percorso).split("\n"):
        trovata = RE_INGEST.match(riga)
        if not trovata:
            continue
        try:
            data = datetime.datetime.strptime(trovata.group(1), "%Y-%m-%d").date()
        except ValueError:
            continue
        if piu_recente is None or data > piu_recente:
            piu_recente = data
    return piu_recente.isoformat() if piu_recente else "nessuno"


def stampa_resoconto(titolo, righe):
    print("=== %s ===" % titolo)
    print()
    for riga in righe:
        print(("  " + riga) if riga else "")
    print()


def errore(messaggio):
    print("ERRORE: " + messaggio, file=sys.stderr)
    return 1


# --------------------------------------------------------------- comandi

def comando_stats(argomenti):
    wiki = Wiki(argomenti.wiki_dir)
    righe = ["wiki-dir: %s" % argomenti.wiki_dir]
    conteggio = {}
    for nome_file in wiki.file_pagine:
        voci = wiki.intestazioni[nome_file] or {}
        tipo = voci.get("type")
        chiave = ("type=%s" % tipo) if tipo else "senza type"
        conteggio[chiave] = conteggio.get(chiave, 0) + 1
    if conteggio:
        # In ordine alfabetico di tipo; le pagine senza tipo in fondo.
        chiavi = sorted(k for k in conteggio if k != "senza type")
        if "senza type" in conteggio:
            chiavi.append("senza type")
        for k in chiavi:
            righe.append("%s: %d" % (k, conteggio[k]))
    else:
        righe.append("Nessuna pagina nel wiki.")
    for cartella in risolvi_cartelle_fonti(argomenti.wiki_dir, argomenti.raw_dir):
        righe.append("fonti (%s): %d" % (cartella, len(fonti_in(cartella))))
    righe.append("")
    righe.append("Totale pagine wiki: %d" % len(wiki.file_pagine))
    data = ultimo_ingest(argomenti.wiki_dir)
    if data is not None:
        righe.append("Ultimo ingest: %s" % data)
    stampa_resoconto("Wiki Stats", righe)
    return 0


def comando_lint(argomenti):
    wiki = Wiki(argomenti.wiki_dir)
    problemi = []
    esterni = []

    # 1. Collegamenti rotti (ed esterni, che non sono problemi).
    for nome_file in wiki.file_pagine:
        for bersaglio in wiki.collegamenti[nome_file]:
            esito = wiki.classifica(bersaglio, nome_file)
            if esito == "rotto":
                problemi.append("LINK ROTTO: [[%s]] in %s" % (bersaglio, nome_file))
            elif esito == "esterno":
                esterni.append("LINK ESTERNO: [[%s]] in %s (nota del vault fuori dal wiki)"
                               % (bersaglio, nome_file))

    # 2. Intestazioni.
    for nome_file in wiki.file_pagine:
        esito = problemi_intestazione(wiki.intestazioni[nome_file])
        if esito == "mancante":
            problemi.append("FRONTMATTER MANCANTE: %s" % nome_file)
        elif esito:
            problemi.append("FRONTMATTER INCOMPLETO: %s manca %s" % (nome_file, esito))

    # 3. Pagine orfane.
    in_entrata = set()
    for nome_file in wiki.file_pagine:
        se_stessa = nome_file[:-3]
        for bersaglio in wiki.collegamenti[nome_file]:
            if bersaglio != se_stessa:
                in_entrata.add(bersaglio)
    percorso_indice = os.path.join(argomenti.wiki_dir, "index.md")
    if os.path.isfile(percorso_indice):
        in_entrata.update(estrai_bersagli(leggi_testo(percorso_indice)))
    for nome_file in wiki.file_pagine:
        nome = nome_file[:-3]
        if nome != PAGINA_RADICE and nome not in in_entrata:
            problemi.append("PAGINA ORFANA: %s (nessun link in entrata; aggiungila a index.md)"
                            % nome)

    # 4. Fonti non processate.
    sintesi = {
        f[:-3] for f in wiki.file_pagine
        if (wiki.intestazioni[f] or {}).get("type") == "source"
    }
    for cartella in risolvi_cartelle_fonti(argomenti.wiki_dir, argomenti.raw_dir):
        etichetta = os.path.basename(os.path.normpath(cartella))
        for nome_file in fonti_in(cartella):
            if nome_file[:-3] not in sintesi:
                problemi.append(
                    "FONTE NON PROCESSATA: %s/%s non ha sintesi (pagina type=source)"
                    % (etichetta, nome_file))

    righe = []
    if problemi:
        righe.extend(problemi)
        righe.append("")
        righe.append("Problemi totali: %d" % len(problemi))
    else:
        righe.append("Nessun problema. Wiki in salute.")
    if esterni:
        righe.append("")
        righe.append("Collegamenti esterni al wiki (solo segnalati, non sono problemi):")
        righe.extend(esterni)
    stampa_resoconto("Wiki Lint", righe)
    return 1 if problemi else 0


def comando_validate(argomenti):
    if not argomenti.pagina:
        return errore("'validate' richiede il nome della pagina.")
    percorso = os.path.join(argomenti.wiki_dir, argomenti.pagina)
    if not os.path.isfile(percorso):
        return errore("pagina non trovata: %s" % percorso)
    wiki = Wiki(argomenti.wiki_dir)
    testo = leggi_testo(percorso)
    problemi = []
    avvisi = []
    esito = problemi_intestazione(leggi_intestazione(testo))
    if esito == "mancante":
        problemi.append("Frontmatter mancante")
    elif esito:
        problemi.append("Campi frontmatter mancanti: %s" % esito)
    for bersaglio in estrai_bersagli(testo):
        stato = wiki.classifica(bersaglio, os.path.basename(percorso))
        if stato == "rotto":
            problemi.append("Link rotto: [[%s]]" % bersaglio)
        elif stato == "esterno":
            avvisi.append("Link esterno al wiki (non e' un problema): [[%s]]" % bersaglio)
    righe = problemi[:] if problemi else ["Pagina valida."]
    righe.extend(avvisi)
    stampa_resoconto("Validate: %s" % argomenti.pagina, righe)
    return 1 if problemi else 0


COMANDI = {"stats": comando_stats, "lint": comando_lint, "validate": comando_validate}


def costruisci_parser():
    parser = argparse.ArgumentParser(
        prog="wiki_ops.py",
        description=(
            "Operazioni deterministiche, in sola lettura, su un wiki piatto e parametrico: "
            "statistiche (stats), controllo di salute (lint), verifica di una pagina (validate)."
        ),
    )
    parser.add_argument("comando", choices=sorted(COMANDI),
                        help="stats, lint oppure validate")
    parser.add_argument("pagina", nargs="?", default=None,
                        help="solo per validate: il file della pagina, relativo a --wiki-dir "
                             "(es. overview.md); ignorato dagli altri comandi")
    parser.add_argument("--wiki-dir", default="02-memoria/wiki",
                        help="cartella del wiki (predefinita: 02-memoria/wiki)")
    parser.add_argument("--raw-dir", action="append", default=None,
                        help="cartella di fonti grezze; ripetibile. Un percorso relativo si "
                             "intende rispetto a --wiki-dir. Se assente: la sottocartella raw "
                             "del wiki")
    return parser


def main(argv=None):
    argomenti = costruisci_parser().parse_args(argv)
    if not os.path.isdir(argomenti.wiki_dir):
        return errore("cartella del wiki non trovata: %s" % argomenti.wiki_dir)
    return COMANDI[argomenti.comando](argomenti)


if __name__ == "__main__":
    sys.exit(main())
