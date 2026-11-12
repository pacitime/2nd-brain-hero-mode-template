# 2nd Brain Hero Mode · Copyright (c) 2026 Alessandro Pacifico (Pacibrand).
# Vedi LICENZA.md nella radice del vault.
"""Test autonomi di wiki_ops.py (niente pytest).

Ogni test costruisce un vault finto in una cartella temporanea e lancia lo strumento
come processo separato, dalla radice del vault finto. Ultima riga: «N/M test passati»;
codice di uscita 1 se qualcosa fallisce.
"""

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import traceback

QUI = os.path.dirname(os.path.abspath(__file__))
STRUMENTO = os.path.normpath(os.path.join(
    QUI, "..", "..", "skills", "llm-wiki", "scripts", "wiki_ops.py"))

WIKI = "02-memoria/wiki"

TESTS = []


def test(funzione):
    TESTS.append(funzione)
    return funzione


# ------------------------------------------------------------ strumenti

def pagina(titolo="T", tipo="concept", created=True, updated=True, corpo="", extra=""):
    righe = ["---", "title: %s" % titolo]
    if tipo is not None:
        righe.append("type: %s" % tipo)
    if created:
        righe.append("created: 2030-01-08")
    if updated:
        righe.append("updated: 2030-01-10")
    if extra:
        righe.append(extra)
    righe.append("---")
    righe.append("")
    righe.append(corpo)
    return "\n".join(righe) + "\n"


class Vault:
    """Vault finto: radice con CLAUDE.md e un wiki in 02-memoria/wiki."""

    def __init__(self, base):
        self.radice = tempfile.mkdtemp(prefix="vault-", dir=base)
        self.scrivi("CLAUDE.md", "# vault finto\n")
        os.makedirs(os.path.join(self.radice, WIKI))

    def scrivi(self, rel, testo):
        percorso = os.path.join(self.radice, rel)
        os.makedirs(os.path.dirname(percorso), exist_ok=True)
        with open(percorso, "w", encoding="utf-8") as f:
            f.write(testo)

    def wiki(self, nome, testo):
        self.scrivi(WIKI + "/" + nome, testo)

    def cartella(self, rel):
        os.makedirs(os.path.join(self.radice, rel), exist_ok=True)

    def lancia(self, *argomenti):
        risultato = subprocess.run(
            [sys.executable, STRUMENTO] + list(argomenti),
            cwd=self.radice, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        return risultato.returncode, risultato.stdout, risultato.stderr

    def impronta(self):
        """Mappa percorso -> (hash, mtime) di tutto il vault, per verificare la sola lettura."""
        stato = {}
        for cartella, sotto, file in os.walk(self.radice):
            stato[cartella] = "dir"
            for n in file:
                p = os.path.join(cartella, n)
                with open(p, "rb") as f:
                    stato[p] = (hashlib.sha256(f.read()).hexdigest(), os.stat(p).st_mtime_ns)
        return stato


def righe_con(testo, etichetta):
    return [r.strip() for r in testo.splitlines() if r.strip().startswith(etichetta)]


def wiki_modello_globale(v):
    """Come il modello del kit: overview, index, log, SCHEMA, raw vuota."""
    v.wiki("overview.md", pagina("Panoramica", "overview", corpo="# Panoramica\n"))
    v.wiki("index.md", "# Indice\n\n- [[overview]]\n")
    v.wiki("log.md", "# Log\n\nFormato: ## [AAAA-MM-GG] ingest: titolo\n")
    v.wiki("SCHEMA.md", "# Schema\n\n`python3 wiki_ops.py lint --wiki-dir ...` e [[inesistente]]\n")
    v.cartella(WIKI + "/raw")


def wiki_misto(v):
    """Caso 12: una pagina buona, una con voce mancante e link rotto, una fonte senza sintesi."""
    v.wiki("buona.md", pagina("Buona", "concept", corpo="Vedi [[altra]]."))
    v.wiki("altra.md", pagina("Altra", "entity", updated=False,
                              corpo="Vedi [[buona]] e [[pagina-che-non-esiste]]."))
    v.wiki("index.md", "- [[buona]]\n- [[altra]]\n")
    v.wiki("log.md", "## [2030-01-08] ingest: prima\n## [2030-01-09] lint: ok\n")
    v.scrivi(WIKI + "/raw/2030-01-08-intervista.md", "fonte\n")


def controlla(condizione, messaggio):
    if not condizione:
        raise AssertionError(messaggio)


# ----------------------------------------------------------------- casi

@test
def caso_01_riga_di_comando_skill():
    v = Vault(BASE)
    wiki_modello_globale(v)
    controlla(os.path.isfile(STRUMENTO), "strumento non trovato in %s" % STRUMENTO)
    controlla(STRUMENTO.replace(os.sep, "/").endswith("skills/llm-wiki/scripts/wiki_ops.py"),
              "percorso inatteso")
    codice, out, err = v.lancia("lint", "--wiki-dir", "02-memoria/wiki")
    controlla(codice in (0, 1) and not err, "la riga di comando della skill non e' valida: %s" % err)


@test
def caso_02_04_05_wiki_modello_globale():
    v = Vault(BASE)
    wiki_modello_globale(v)
    codice, out, _ = v.lancia("lint", "--wiki-dir", WIKI)
    controlla(codice == 0 and "Wiki in salute" in out, "lint modello: %d %s" % (codice, out))
    codice, out, _ = v.lancia("stats", "--wiki-dir", WIKI)
    controlla(codice == 0, "stats codice")
    controlla("type=overview: 1" in out, out)
    controlla("Totale pagine wiki: 1" in out, out)
    controlla("Ultimo ingest: nessuno" in out, out)
    controlla(righe_con(out, "fonti (") and righe_con(out, "fonti (")[0].endswith(": 0"), out)
    codice, out, _ = v.lancia("validate", "overview.md", "--wiki-dir", WIKI)
    controlla(codice == 0 and "Pagina valida." in out, out)


@test
def caso_03_wiki_modello_progetto():
    v = Vault(BASE)
    base = "10-lavoro/p/knowledge"
    v.scrivi(base + "/wiki/overview.md", pagina("P", "overview"))
    v.scrivi(base + "/wiki/index.md", "- [[overview]]\n")
    v.scrivi(base + "/wiki/log.md", "# log\n")
    v.cartella(base + "/raw")
    v.cartella(base + "/calls")
    codice, out, _ = v.lancia("lint", "--wiki-dir", base + "/wiki",
                              "--raw-dir", "../raw", "--raw-dir", "../calls")
    controlla(codice == 0 and "Wiki in salute" in out, out)


@test
def caso_06_validate_senza_pagina():
    v = Vault(BASE)
    wiki_modello_globale(v)
    codice, out, err = v.lancia("validate", "--wiki-dir", WIKI)
    controlla(codice == 1, "codice %d" % codice)
    controlla("richiede il nome della pagina" in err and len(err.strip().splitlines()) == 1, err)


@test
def caso_07_validate_inesistente():
    v = Vault(BASE)
    wiki_modello_globale(v)
    codice, out, err = v.lancia("validate", "manca.md", "--wiki-dir", WIKI)
    controlla(codice == 1, "codice")
    controlla("pagina non trovata" in err and "02-memoria/wiki/manca.md" in err, err)


@test
def caso_08_09_errori_uso():
    v = Vault(BASE)
    wiki_modello_globale(v)
    for argomenti in ([], ["boh"], ["lint", "--boh"]):
        codice, out, err = v.lancia(*argomenti)
        controlla(codice == 2, "%s -> codice %d" % (argomenti, codice))
        controlla("usage" in err.lower() and out == "", "%s -> %r" % (argomenti, err))


@test
def caso_10_11_wiki_inesistente_e_errore():
    # Decisione della riscrittura: un wiki inesistente e' un errore, codice 1, su stderr.
    v = Vault(BASE)
    for comando in ("lint", "stats", "validate"):
        argomenti = [comando] + (["x.md"] if comando == "validate" else [])
        codice, out, err = v.lancia(*(argomenti + ["--wiki-dir", "non/esiste"]))
        controlla(codice == 1, "%s codice %d" % (comando, codice))
        controlla("non/esiste" in err and "ERRORE" in err and out == "", "%s: %r %r" % (comando, out, err))


@test
def caso_12_lint_misto():
    v = Vault(BASE)
    wiki_misto(v)
    codice, out, _ = v.lancia("lint", "--wiki-dir", WIKI)
    controlla(codice == 1, "codice")
    controlla(righe_con(out, "LINK ROTTO") == ["LINK ROTTO: [[pagina-che-non-esiste]] in altra.md"], out)
    controlla(righe_con(out, "FRONTMATTER INCOMPLETO") ==
              ["FRONTMATTER INCOMPLETO: altra.md manca ['updated']"], out)
    controlla(len(righe_con(out, "FONTE NON PROCESSATA")) == 1, out)
    controlla("raw/2030-01-08-intervista.md" in out, out)
    controlla("Problemi totali: 3" in out, out)


@test
def caso_13_validate_buona_e_rotta():
    v = Vault(BASE)
    wiki_misto(v)
    codice, out, _ = v.lancia("validate", "buona.md", "--wiki-dir", WIKI)
    controlla(codice == 0 and "Pagina valida." in out and "Validate: buona.md" in out, out)
    codice, out, _ = v.lancia("validate", "altra.md", "--wiki-dir", WIKI)
    controlla(codice == 1, "codice")
    contenuto = [r for r in out.splitlines()[1:] if r.strip()]
    controlla(len(contenuto) == 2, out)
    controlla("Campi frontmatter mancanti: ['updated']" in out, out)
    controlla("Link rotto: [[pagina-che-non-esiste]]" in out, out)


@test
def caso_14_stats_misto():
    v = Vault(BASE)
    wiki_misto(v)
    codice, out, _ = v.lancia("stats", "--wiki-dir", WIKI)
    controlla(codice == 0, "codice")
    controlla("Totale pagine wiki: 2" in out, out)
    controlla(righe_con(out, "fonti (")[0].endswith(": 1"), out)
    controlla("Ultimo ingest: 2030-01-08" in out, out)


@test
def caso_15_16_17_18_19_intestazioni():
    v = Vault(BASE)
    v.wiki("senza.md", "# niente intestazione\n")
    v.wiki("riga-vuota.md", "\n" + pagina("X"))
    v.wiki("vuota.md", "---\n---\n\ncorpo\n")
    v.wiki("parziale.md", pagina("P", "concept", created=False, updated=False))
    v.wiki("valore-vuoto.md", pagina("V", "concept", updated=False, extra="updated:"))
    v.wiki("index.md", "".join("[[%s]]\n" % n for n in
                               ("senza", "riga-vuota", "vuota", "parziale", "valore-vuoto")))
    _, out, _ = v.lancia("lint", "--wiki-dir", WIKI)
    mancanti = righe_con(out, "FRONTMATTER MANCANTE")
    controlla(mancanti == ["FRONTMATTER MANCANTE: riga-vuota.md", "FRONTMATTER MANCANTE: senza.md",
                           "FRONTMATTER MANCANTE: vuota.md"], out)
    controlla(righe_con(out, "FRONTMATTER INCOMPLETO") ==
              ["FRONTMATTER INCOMPLETO: parziale.md manca ['created', 'updated']"], out)
    controlla("valore-vuoto" not in out, out)


@test
def caso_20_27_collegamenti():
    v = Vault(BASE)
    v.wiki("pagina-uno.md", pagina("Uno"))
    v.wiki("2030-01-08-intervista.md", pagina("Sintesi", "source"))
    v.scrivi(WIKI + "/raw/2030-01-08-intervista.md", "x\n")
    v.scrivi(WIKI + "/raw/2030-02-01-altra.md", "x\n")
    corpo = ("[[pagina-uno|il testo]] [[ pagina-uno ]] [[Pagina-Uno]] [[index]] [[log]] "
             "[[2030-01-08-intervista]] [[2030-02-01-altra]] [[doppio]] [[doppio]]")
    v.wiki("prova.md", pagina("Prova", extra="related: [[rotto-in-related]]", corpo=corpo))
    v.wiki("index.md", "[[prova]]\n")
    _, out, _ = v.lancia("lint", "--wiki-dir", WIKI)
    rotti = righe_con(out, "LINK ROTTO")
    attesi = ["LINK ROTTO: [[%s]] in prova.md" % b for b in
              ("rotto-in-related", "Pagina-Uno", "index", "log", "2030-02-01-altra",
               "doppio", "doppio")]
    controlla(sorted(rotti) == sorted(attesi), "\n".join(rotti))
    controlla("[[pagina-uno]]" not in out and "2030-01-08-intervista]]" not in out, out)


@test
def caso_26_link_in_related_vale_in_entrata():
    v = Vault(BASE)
    v.wiki("a.md", pagina("A", extra="related: [[b]]"))
    v.wiki("b.md", pagina("B"))
    v.wiki("index.md", "[[a]]\n")
    codice, out, _ = v.lancia("lint", "--wiki-dir", WIKI)
    controlla(codice == 0 and not righe_con(out, "PAGINA ORFANA"), out)


@test
def caso_collegamento_con_sezione():
    v = Vault(BASE)
    v.wiki("a.md", pagina("A", corpo="[[b#Dettagli]] [[b#Altro|testo]] [[#sezione-interna]] [[c#x]]"))
    v.wiki("b.md", pagina("B"))
    v.wiki("index.md", "[[a]]\n")
    codice, out, _ = v.lancia("lint", "--wiki-dir", WIKI)
    controlla(righe_con(out, "LINK ROTTO") == ["LINK ROTTO: [[c]] in a.md"], out)
    controlla(not righe_con(out, "PAGINA ORFANA"), "b deve avere un link in entrata: " + out)
    controlla(codice == 1, "codice")


@test
def caso_collegamenti_esterni_nel_vault():
    v = Vault(BASE)
    v.scrivi("10-lavoro/ClienteAlfa/README.md", "# progetto\n")
    v.scrivi("30-personale/Nota Lunga.md", "# nota\n")
    v.scrivi("_local-only/segreta.md", "x\n")
    v.wiki("a.md", pagina("A", corpo="[[Nota Lunga]] [[ClienteAlfa/README]] [[README#stato]] [[segreta]]"))
    v.wiki("index.md", "[[a]]\n")
    codice, out, _ = v.lancia("lint", "--wiki-dir", WIKI)
    esterni = righe_con(out, "LINK ESTERNO")
    controlla(len(esterni) == 3, out)
    controlla(righe_con(out, "LINK ROTTO") == ["LINK ROTTO: [[segreta]] in a.md"], out)
    controlla("Problemi totali: 1" in out and codice == 1, out)
    # Solo esterni: il controllo non fallisce.
    v.wiki("a.md", pagina("A", corpo="[[Nota Lunga]]"))
    codice, out, _ = v.lancia("lint", "--wiki-dir", WIKI)
    controlla(codice == 0 and "Wiki in salute" in out and righe_con(out, "LINK ESTERNO"), out)
    codice, out, _ = v.lancia("validate", "a.md", "--wiki-dir", WIKI)
    controlla(codice == 0 and "Pagina valida." in out and "[[Nota Lunga]]" in out, out)


@test
def caso_28_32_orfane():
    v = Vault(BASE)
    v.wiki("sola.md", pagina("S", corpo="[[sola]]"))
    v.wiki("in-indice.md", pagina("I"))
    v.wiki("citata.md", pagina("C"))
    v.wiki("citante.md", pagina("Ct", corpo="[[citata]]"))
    v.wiki("nel-log.md", pagina("L"))
    v.wiki("nello-schema.md", pagina("Sc"))
    v.wiki("overview.md", pagina("O", "overview"))
    v.wiki("index.md", "[[in-indice]] [[citante]]\n")
    v.wiki("log.md", "## [2030-01-01] ingest: [[nel-log]]\n")
    v.wiki("SCHEMA.md", "[[nello-schema]]\n")
    _, out, _ = v.lancia("lint", "--wiki-dir", WIKI)
    orfane = sorted(r.split()[2] for r in righe_con(out, "PAGINA ORFANA"))
    controlla(orfane == ["nel-log", "nello-schema", "sola"], out)
    controlla("index.md" in righe_con(out, "PAGINA ORFANA")[0], "manca il rimedio")


@test
def caso_33_35_fonti_e_tipo():
    for tipo, attesa in (("source", 0), ("concept", 1), ('"source"', 1)):
        v = Vault(BASE)
        v.wiki("2030-01-08-intervista.md", pagina("S", tipo))
        v.wiki("index.md", "[[2030-01-08-intervista]]\n")
        v.scrivi(WIKI + "/raw/2030-01-08-intervista.md", "x\n")
        _, out, _ = v.lancia("lint", "--wiki-dir", WIKI)
        controlla(len(righe_con(out, "FONTE NON PROCESSATA")) == attesa, "%s: %s" % (tipo, out))


@test
def caso_36_raw_dir_relativo_e_ripetuto():
    v = Vault(BASE)
    base = "10-lavoro/p/knowledge"
    v.scrivi(base + "/wiki/overview.md", pagina("P", "overview"))
    v.scrivi(base + "/raw/2030-01-01-fonte.md", "x\n")
    v.scrivi(base + "/calls/2030-01-02-call.md", "x\n")
    v.scrivi(base + "/wiki/raw/2030-01-03-ignorata.md", "x\n")
    codice, out, _ = v.lancia("lint", "--wiki-dir", base + "/wiki",
                              "--raw-dir", "../raw", "--raw-dir", "../calls")
    righe = righe_con(out, "FONTE NON PROCESSATA")
    controlla(codice == 1 and len(righe) == 2, out)
    controlla(righe[0].startswith("FONTE NON PROCESSATA: raw/2030-01-01-fonte.md"), out)
    controlla(righe[1].startswith("FONTE NON PROCESSATA: calls/2030-01-02-call.md"), out)
    controlla("ignorata" not in out, "caso 38: la raw del wiki non va guardata")
    # Caso 50 ribaltato dalla decisione: ../raw e' relativo al wiki, quindi si trova.
    codice, out, _ = v.lancia("stats", "--wiki-dir", base + "/wiki", "--raw-dir", "../raw")
    controlla(righe_con(out, "fonti (")[0].endswith(": 1"), out)
    # Percorso assoluto: usato cosi' com'e'.
    assoluto = os.path.join(v.radice, base, "calls")
    _, out, _ = v.lancia("lint", "--wiki-dir", base + "/wiki", "--raw-dir", assoluto)
    controlla(len(righe_con(out, "FONTE NON PROCESSATA: calls/")) == 1, out)


@test
def caso_37_38_39_raw_predefinita_e_inesistente():
    v = Vault(BASE)
    v.wiki("overview.md", pagina("O", "overview"))
    v.scrivi(WIKI + "/raw/2030-01-01-fonte.md", "x\n")
    v.scrivi(WIKI + "/raw/.gitkeep", "")
    _, out, _ = v.lancia("lint", "--wiki-dir", WIKI)
    controlla(len(righe_con(out, "FONTE NON PROCESSATA: raw/")) == 1, out)
    v.cartella("altre")
    codice, out, err = v.lancia("lint", "--wiki-dir", WIKI, "--raw-dir", "../../altre")
    controlla(codice == 0 and not righe_con(out, "FONTE"), out)
    codice, out, err = v.lancia("lint", "--wiki-dir", WIKI, "--raw-dir", "non-esiste")
    controlla(codice == 0 and not err and not righe_con(out, "FONTE"), out + err)
    codice, out, _ = v.lancia("stats", "--wiki-dir", WIKI, "--raw-dir", "non-esiste")
    controlla(righe_con(out, "fonti (")[0].endswith(": 0"), out)


@test
def caso_40_sottocartelle():
    v = Vault(BASE)
    v.wiki("overview.md", pagina("O", "overview", corpo="[[nascosta]]"))
    v.wiki("sotto/nascosta.md", "senza intestazione\n")
    codice, out, _ = v.lancia("lint", "--wiki-dir", WIKI)
    controlla(righe_con(out, "LINK ROTTO") == ["LINK ROTTO: [[nascosta]] in overview.md"], out)
    controlla("FRONTMATTER" not in out, out)
    _, out, _ = v.lancia("stats", "--wiki-dir", WIKI)
    controlla("Totale pagine wiki: 1" in out, out)


@test
def caso_41_stats_tipi():
    v = Vault(BASE)
    for n in ("c1", "c2", "c3"):
        v.wiki(n + ".md", pagina(n, "concept"))
    v.wiki("s.md", pagina("s", "source"))
    v.wiki("x.md", pagina("x", None))
    _, out, _ = v.lancia("stats", "--wiki-dir", WIKI)
    tipi = [r for r in (x.strip() for x in out.splitlines())
            if r.startswith("type=") or r.startswith("senza type")]
    controlla(tipi == ["type=concept: 3", "type=source: 1", "senza type: 1"], out)
    controlla("Totale pagine wiki: 5" in out, out)


@test
def caso_42_44_ultimo_ingest():
    for log, atteso in (
        # Dal piu' vecchio al piu' nuovo (registro scritto in fondo).
        ("## [2030-01-05] ingest: a\n## [2030-01-10] ingest: b\n", "2030-01-10"),
        # Dal piu' nuovo al piu' vecchio (registro scritto in cima).
        ("## [2030-01-10] ingest: b\n## [2030-01-05] ingest: a\n## [2029-12-31] ingest: z\n",
         "2030-01-10"),
        # Misto, con lint piu' recenti che non contano.
        ("## [2030-01-07] ingest: c\n## [2030-02-01] lint: x\n## [2030-01-05] ingest: a\n"
         "## [2030-01-20] ingest: d\n## [2030-01-09] ingest: b\n", "2030-01-20"),
        # Date non valide ignorate anche se sarebbero le piu' recenti.
        ("## [2030-01-05] ingest: a\n## [2030-13-45] ingest: rotta\n## [2030-02-30] ingest: no\n",
         "2030-01-05"),
        ("## [2030-13-45] ingest: rotta\n", "nessuno"),
        ("Formato: ## [AAAA-MM-GG] ingest: titolo\n## [AAAA-MM-GG] ingest: titolo\n", "nessuno"),
        ("## [2030-01-05] lint: a\n## [2030-01-06] lint: b\n", "nessuno"),
    ):
        v = Vault(BASE)
        v.wiki("log.md", log)
        _, out, _ = v.lancia("stats", "--wiki-dir", WIKI)
        controlla("Ultimo ingest: %s" % atteso in out, "%r -> %s" % (log, out))
    v = Vault(BASE)
    v.wiki("overview.md", pagina("O", "overview"))
    _, out, _ = v.lancia("stats", "--wiki-dir", WIKI)
    controlla("Ultimo ingest" not in out, "senza log.md la riga non compare")


@test
def caso_45_validate_index():
    v = Vault(BASE)
    wiki_modello_globale(v)
    codice, out, _ = v.lancia("validate", "index.md", "--wiki-dir", WIKI)
    controlla(codice == 1 and "Frontmatter mancante" in out, out)


@test
def caso_46_pagina_ignorata_dagli_altri():
    v = Vault(BASE)
    wiki_misto(v)
    a = v.lancia("lint", "--wiki-dir", WIKI)
    b = v.lancia("lint", "overview.md", "--wiki-dir", WIKI)
    controlla(a == b, "lint con pagina diverso da lint senza")


@test
def caso_47_48_sola_lettura_e_stabilita():
    v = Vault(BASE)
    wiki_misto(v)
    v.scrivi("30-personale/Nota Esterna.md", "x\n")
    v.wiki("buona.md", pagina("Buona", corpo="[[altra]] [[Nota Esterna]]"))
    prima = v.impronta()
    risultati = []
    for _ in range(2):
        for argomenti in (["stats"], ["lint"], ["validate", "altra.md"], ["validate"],
                          ["validate", "manca.md"]):
            risultati.append(v.lancia(*(argomenti + ["--wiki-dir", WIKI])))
    controlla(v.impronta() == prima, "lo strumento ha modificato il vault")
    meta = len(risultati) // 2
    controlla(risultati[:meta] == risultati[meta:], "due lanci danno risultati diversi")


@test
def caso_49_aiuto():
    v = Vault(BASE)
    codice, out, _ = v.lancia("-h")
    controlla(codice == 0, "codice")
    for parola in ("stats", "lint", "validate", "--wiki-dir", "--raw-dir", "02-memoria/wiki",
                   "ripetibile", "pagina"):
        controlla(parola in out, "manca %r nell'aiuto" % parola)


@test
def caso_wiki_vuoto_e_senza_index():
    v = Vault(BASE)
    wiki_modello_globale(v)
    os.remove(os.path.join(v.radice, WIKI, "overview.md"))
    codice, out, _ = v.lancia("lint", "--wiki-dir", WIKI)
    controlla(codice == 0 and "Wiki in salute" in out, out)
    _, out, _ = v.lancia("stats", "--wiki-dir", WIKI)
    controlla("Nessuna pagina" in out and "Totale pagine wiki: 0" in out, out)
    v2 = Vault(BASE)
    v2.wiki("a.md", pagina("A", corpo="[[b]]"))
    v2.wiki("b.md", pagina("B", corpo="[[a]]"))
    codice, out, _ = v2.lancia("lint", "--wiki-dir", WIKI)
    controlla(codice == 0, "senza index i link fra pagine bastano: " + out)


@test
def caso_ordine_alfabetico():
    v = Vault(BASE)
    for n in ("zeta", "alfa", "emme"):
        v.wiki(n + ".md", "senza intestazione [[rotto-%s]]\n" % n)
    _, out, _ = v.lancia("lint", "--wiki-dir", WIKI)
    controlla(righe_con(out, "FRONTMATTER MANCANTE") == sorted(righe_con(out, "FRONTMATTER MANCANTE")), out)
    controlla(righe_con(out, "LINK ROTTO") == sorted(righe_con(out, "LINK ROTTO")), out)
    controlla(righe_con(out, "PAGINA ORFANA") == sorted(righe_con(out, "PAGINA ORFANA")), out)


@test
def caso_nessun_trattino_lungo():
    for percorso in (STRUMENTO, os.path.abspath(__file__)):
        with open(percorso, encoding="utf-8") as f:
            controlla(chr(0x2014) not in f.read(), "trattino lungo in %s" % percorso)


# ------------------------------------------------------------- esecuzione

def main():
    global BASE
    BASE = tempfile.mkdtemp(prefix="test-wiki-ops-")
    passati = 0
    try:
        for t in TESTS:
            try:
                t()
                passati += 1
                print("ok    %s" % t.__name__)
            except Exception:
                print("FALLITO %s" % t.__name__)
                traceback.print_exc(limit=1, file=sys.stdout)
    finally:
        shutil.rmtree(BASE, ignore_errors=True)
    print("%d/%d test passati" % (passati, len(TESTS)))
    return 0 if passati == len(TESTS) else 1


BASE = None

if __name__ == "__main__":
    sys.exit(main())
