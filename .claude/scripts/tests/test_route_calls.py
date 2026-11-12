# 2nd Brain Hero Mode · Copyright (c) 2026 Alessandro Pacifico (Pacibrand).
# Vedi LICENZA.md nella radice del vault.
"""
Test del router di auto-smistamento call (route_calls.py). Vault finto in tmp, nessun token.

La mappa dei progetti e' INIETTATA qui sotto (progetti inventati): il test non dipende da
`.claude/config/brain.json`, quindi passa uguale su un vault appena creato e su uno pieno.

    python3 .claude/scripts/tests/test_route_calls.py
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))

import brain_config  # noqa: E402
import route_calls as rc  # noqa: E402

OK, KO = "[OK ]", "[FAIL]"
results: list[tuple[bool, str]] = []
vaults: list[Path] = []

# Mappa di prova, nello stesso formato di brain_config.routing(). Tre progetti inventati piu' una
# rotta extra con destinazione dichiarata per intero.
TEST_ROUTING: list[dict] = [
    {
        "project": "studio-alfa",
        "dest": ("10-lavoro", "clienti", "studio-alfa", "knowledge", "calls"),
        "keywords": ["studio alfa", "planimetri", "cantiere", "ristrutturazion", "capitolato"],
        "title_only": [],
    },
    {
        "project": "corso-beta",
        "dest": ("10-lavoro", "corso-beta", "knowledge", "calls"),
        "keywords": ["corso beta", "iscrizion", "lezion", "dispensa", "aula virtuale"],
        "title_only": [],
    },
    {
        "project": "orto-gamma",
        "dest": ("10-lavoro", "orto-gamma", "knowledge", "calls"),
        "keywords": ["orto gamma", "compost", "irrigazion", "vivaio", "semenzaio"],
        # Parole che in un titolo sono la notizia e in un transcript sono chiacchiera.
        "title_only": ["raccolto", "serra", "semina"],
    },
    {
        "project": "fiscale-legale",
        "dest": ("20-fiscale-legale", "calls"),
        # Nel corpo si fidano solo i tecnicismi: nessuno li dice per caso.
        "keywords": ["commercialista", "partita iva", "dichiarazione dei redditi", "ritenuta d'acconto"],
        "title_only": ["fiscale", "tasse", "contratto"],
    },
]
rc.ROUTING = TEST_ROUTING


def check(cond: bool, label: str) -> None:
    results.append((bool(cond), label))
    print(f"  {OK if cond else KO} {label}")


def make_vault() -> Path:
    root = Path(tempfile.mkdtemp(prefix="route-test-"))
    (root / "00-inbox" / "calls").mkdir(parents=True)
    vaults.append(root)
    return root


def put_call(root: Path, name: str, content: str) -> None:
    (root / "00-inbox" / "calls" / name).write_text(content, encoding="utf-8")


def fm(title: str, body: str = "corpo call generico") -> str:
    return f"---\ntitle: {title}\n---\n\n# {title}\n\n{body}\n"


def in_inbox(root: Path, name: str) -> bool:
    return (root / "00-inbox" / "calls" / name).exists()


# ---------- 1. classify: match netto per progetto ----------
print("\n[1] classify: vincitore netto")
check(rc.classify("Studio Alfa: planimetrie e stato del cantiere", "") == "studio-alfa",
      "titolo con le parole di studio-alfa → studio-alfa")
check(rc.classify("Iscrizioni e calendario delle lezioni", "") == "corso-beta",
      "titolo con le parole di corso-beta → corso-beta")
check(rc.classify("Impianto di irrigazione e nuovo vivaio", "") == "orto-gamma",
      "titolo con le parole di orto-gamma → orto-gamma")

# ---------- 2. classify: ambiguo → None ----------
print("\n[2] classify: ambiguo o nessun match → None")
check(rc.classify("Call conoscitiva con un fornitore", "parliamo di preventivi e tempi di consegna") is None,
      "nessuna parola chiave di progetto → None (resta in inbox)")
check(rc.classify("Chiamata generica", "") is None, "titolo generico → None")
check(rc.classify("Cantiere e lezioni: punto della settimana", "") is None,
      "titolo che nomina due progetti alla pari → None (nessun margine)")

# ---------- 3. route: sposta i netti, lascia gli ambigui ----------
print("\n[3] route: sposta i netti, lascia gli ambigui")
root = make_vault()
put_call(root, "2030-01-09-cantiere-studio-alfa.md", fm("Stato del cantiere con Studio Alfa"))
put_call(root, "2030-01-10-iscrizioni-lezioni.md", fm("Iscrizioni e lezioni di febbraio"))
put_call(root, "2030-01-11-fornitore.md", fm("Call conoscitiva con un fornitore", "preventivi"))
put_call(root, "README.md", "readme, non è una call")

res = rc.route(root)
routed_names = {n for n, _ in res["routed"]}
check("2030-01-09-cantiere-studio-alfa.md" in routed_names, "call di studio-alfa smistata")
check("2030-01-10-iscrizioni-lezioni.md" in routed_names, "call di corso-beta smistata")
check("2030-01-11-fornitore.md" in res["ambiguous"], "call ambigua lasciata in inbox")
check("README.md" not in routed_names and all("README" not in n for n in res["ambiguous"]),
      "README.md ignorato")

# file effettivamente spostati / rimasti
alfa = root / "10-lavoro" / "clienti" / "studio-alfa" / "knowledge" / "calls"
beta = root / "10-lavoro" / "corso-beta" / "knowledge" / "calls"
check((alfa / "2030-01-09-cantiere-studio-alfa.md").exists(), "file di studio-alfa creato a destinazione")
check((beta / "2030-01-10-iscrizioni-lezioni.md").exists(), "file di corso-beta creato a destinazione")
check(in_inbox(root, "2030-01-11-fornitore.md"), "ambigua ancora in inbox")
check(not in_inbox(root, "2030-01-09-cantiere-studio-alfa.md"), "la call smistata NON è più in inbox")

# ---------- 4. dry-run non muove nulla ----------
print("\n[4] --preview (dry-run) non muove nulla")
root2 = make_vault()
put_call(root2, "2030-01-09-capitolato.md", fm("Capitolato e planimetrie da rivedere"))
res2 = rc.route(root2, dry_run=True)
check(len(res2["routed"]) == 1, "dry-run riporta 1 call da smistare")
check(in_inbox(root2, "2030-01-09-capitolato.md"), "dry-run: il file è ancora in inbox (non spostato)")

# ---------- 5. no-clobber: se esiste già a destinazione → skip ----------
print("\n[5] no-clobber: destinazione già occupata → skip")
root3 = make_vault()
dest = root3 / "10-lavoro" / "corso-beta" / "knowledge" / "calls"
dest.mkdir(parents=True)
(dest / "2030-01-10-lezioni.md").write_text("già qui", encoding="utf-8")
put_call(root3, "2030-01-10-lezioni.md", fm("Lezioni e iscrizioni"))
res3 = rc.route(root3)
check(any("2030-01-10-lezioni.md" == n for n, _ in res3["skipped"]),
      "call con nome già presente a destinazione → skip (no overwrite)")
check(in_inbox(root3, "2030-01-10-lezioni.md"), "l'originale resta in inbox (non sovrascrive)")
check((dest / "2030-01-10-lezioni.md").read_text(encoding="utf-8") == "già qui",
      "il file a destinazione non è stato toccato")

# ---------- 6. il titolo comanda sul corpo ----------
print("\n[6] titolo e corpo: il corpo non elegge da solo")

# Una call sui conti nomina per forza i progetti di cui fa i conti: due parole di un altro
# progetto nel corpo non devono portarsela via.
TAX_TITLE = "Pianificazione fiscale dell'anno e tasse da versare"
TAX_BODY = ("Rivediamo i costi di compost e irrigazione sostenuti nell'anno e come metterli a "
            "bilancio. Poi le scadenze dei versamenti.")
check(rc.score_projects(TAX_TITLE, TAX_BODY)["orto-gamma"] == 2,
      "premessa: il corpo da solo porta l'altro progetto a 2 (la vecchia soglia)")
check(rc.classify(TAX_TITLE, TAX_BODY) == "fiscale-legale",
      "call fiscale con le parole di un altro progetto nel corpo → fiscale-legale")

# Il corpo non puo' scavalcare un titolo che nomina un altro progetto.
check(rc.classify("Iscrizioni al corso beta", "parliamo anche di compost, irrigazione, vivaio e semenzaio")
      != "orto-gamma",
      "titolo di corso-beta + corpo di orto-gamma → il corpo non scavalca il titolo")
check(rc.classify("Aula virtuale", "compost, irrigazione, vivaio, semenzaio e orto gamma") is None,
      "titolo che nomina un progetto, corpo che ne premia un altro → None (resta in inbox)")

# Le title_only non contano nel corpo: chiacchiera in un transcript non e' l'argomento della call.
check(rc.classify("Idee per il calendario dell'autunno",
                  "prima della pianificazione fiscale sto tranquillo, poi vediamo tasse e contratto")
      != "fiscale-legale",
      "'fiscale'/'tasse'/'contratto' solo nel corpo → NON bastano per la rotta fiscale")

# ...ma nel titolo si'.
check(rc.classify("Pianificazione fiscale e contratto di affitto", "") == "fiscale-legale",
      "'fiscale'/'contratto' nel TITOLO → fiscale-legale")

# I tecnicismi restano affidabili anche nel corpo: nessuno li dice per caso.
check(rc.classify("Call con il consulente", "partita iva, dichiarazione dei redditi "
                  "e ritenuta d'acconto") == "fiscale-legale",
      "titolo muto + tecnicismi nel corpo → il corpo decide (richiamo preservato)")

# Il titolo muto NON deve azzerare il router: e' il caso della maggioranza delle call.
check(rc.classify("Call con Anna", "compost, irrigazione e il nuovo vivaio") == "orto-gamma",
      "titolo che non nomina nulla → il corpo decide (nessuna regressione di richiamo)")

# ---------- 7. title_only: valgono nel titolo, zero nel corpo ----------
print("\n[7] title_only")
check(rc.classify("Organizzazione turni: obiettivo raccolto di settembre", "") == "orto-gamma",
      "'raccolto' nel titolo → orto-gamma")
check(rc.classify("Call con Luca", "ho visto il raccolto, la serra e la semina di un vicino") != "orto-gamma",
      "'raccolto'/'serra'/'semina' solo nel corpo → NON eleggono orto-gamma")
check(rc.score_projects("Call con Luca", "raccolto, serra, semina")["orto-gamma"] == 0,
      "title_only nel corpo valgono zero")

# ---------- 8. quarantena salute ----------
print("\n[8] quarantena salute (dal titolo)")
root4 = make_vault()
put_call(root4, "2030-02-08-visita.md", fm("Visita medica: esito delle analisi"))
put_call(root4, "2030-02-09-vivaio.md", fm("Nuovo vivaio e irrigazione"))
res4 = rc.route(root4)
priv4 = root4 / "_local-only" / "calls"
check(res4["private"] == ["2030-02-08-visita.md"], "call medica riconosciuta come privata")
check((priv4 / "2030-02-08-visita.md").exists(), "call medica spostata in _local-only/calls (fuori dal repo)")
check(not in_inbox(root4, "2030-02-08-visita.md"),
      "call medica non resta in inbox (il backup orario la pubblicherebbe)")
check(("2030-02-09-vivaio.md", "orto-gamma") in res4["routed"], "la call di lavoro accanto è smistata come sempre")
check(rc.is_health("Visita dal dottore") and rc.is_health("Post-op check with the doctor")
      and not rc.is_health("Nuovo vivaio e irrigazione"),
      "is_health: titoli medici sì, di lavoro no")
check(rc.route(make_vault()) == {"routed": [], "ambiguous": [], "skipped": [], "private": []},
      "inbox vuota → risultato vuoto")
# la salute vince anche su un titolo che nomina un progetto
root4b = make_vault()
put_call(root4b, "2030-02-10-mista.md", fm("Cantiere e terapia: punto della settimana"))
res4b = rc.route(root4b, dry_run=True)
check(res4b["private"] == ["2030-02-10-mista.md"] and not res4b["routed"],
      "titolo con un progetto E una parola sanitaria → quarantena, non progetto")
check(in_inbox(root4b, "2030-02-10-mista.md") and not (root4b / "_local-only").exists(),
      "dry-run: la call sanitaria è elencata ma non spostata")

# ---------- 9. quarantena a mano ----------
print("\n[9] quarantena a mano (elenco in .claude/data/quarantena-call.txt)")
root5 = make_vault()
put_call(root5, "2030-03-01-cantiere.md", fm("Stato del cantiere e capitolato"))
put_call(root5, "2030-03-02-lezioni.md", fm("Lezioni e iscrizioni di marzo"))
(root5 / ".claude" / "data").mkdir(parents=True)
(root5 / ".claude" / "data" / "quarantena-call.txt").write_text(
    "# una riga per file\n\n2030-03-01-cantiere.md\n# 2030-03-02-lezioni.md\n", encoding="utf-8")
check(rc.manual_quarantine(root5) == ["2030-03-01-cantiere.md"],
      "elenco letto: righe vuote e commenti saltati")
res5 = rc.route(root5)
check(res5["private"] == ["2030-03-01-cantiere.md"], "call in elenco → quarantena, anche col titolo di lavoro")
check((root5 / "_local-only" / "calls" / "2030-03-01-cantiere.md").exists(),
      "call in elenco spostata in _local-only/calls")
check(not (root5 / "10-lavoro" / "clienti" / "studio-alfa").exists(), "e NON nel progetto che il titolo nomina")
check(("2030-03-02-lezioni.md", "corso-beta") in res5["routed"],
      "la call commentata nell'elenco segue la strada normale")
check(rc.manual_quarantine(make_vault()) == [], "elenco assente → nessuna quarantena a mano, nessun errore")

# ---------- 10. nessun progetto configurato ----------
print("\n[10] mappa vuota: tutto resta in inbox, nessun errore")
rc.ROUTING = []
root6 = make_vault()
put_call(root6, "2030-04-01-cantiere.md", fm("Stato del cantiere con Studio Alfa", "planimetrie"))
put_call(root6, "2030-04-02-qualsiasi.md", fm("Una call qualsiasi"))
put_call(root6, "2030-04-03-dottore.md", fm("Visita dal dottore"))
check(rc.classify("Stato del cantiere con Studio Alfa", "planimetrie") is None, "classify con mappa vuota → None")
res6 = rc.route(root6)
check(res6["routed"] == [] and res6["skipped"] == [], "nessuna call smistata")
check(res6["ambiguous"] == ["2030-04-01-cantiere.md", "2030-04-02-qualsiasi.md"],
      "tutte le call di lavoro restano in inbox come ambigue")
check(res6["private"] == ["2030-04-03-dottore.md"], "la quarantena salute funziona anche senza progetti")
check("Call ambigue, da smistare a mano (2)" in rc.render(res6), "il riassunto le elenca come ambigue")
rc.ROUTING = TEST_ROUTING

# ---------- 11. la mappa scritta in brain.json arriva nel formato del router ----------
print("\n[11] brain_config.routing(): dal JSON alla mappa")
root7 = make_vault()
(root7 / ".claude" / "config").mkdir(parents=True)
(root7 / ".claude" / "config" / "brain.json").write_text(json.dumps({
    "projects": [{"id": "studio-alfa", "path": "10-lavoro/clienti/studio-alfa",
                  "keywords": ["Studio Alfa", "Cantiere"], "title_only": ["Sopralluogo"]}],
    "extra_routes": [{"id": "fiscale-legale", "dest": "20-fiscale-legale/calls",
                      "keywords": ["commercialista"], "title_only": ["fiscale"]}],
}), encoding="utf-8")
mappa = brain_config.routing(root7)
check([m["project"] for m in mappa] == ["studio-alfa", "fiscale-legale"], "progetti e rotte extra, nell'ordine")
check(mappa[0]["dest"] == ("10-lavoro", "clienti", "studio-alfa", "knowledge", "calls"),
      "un progetto va in <path>/knowledge/calls")
check(mappa[1]["dest"] == ("20-fiscale-legale", "calls"), "una rotta extra dichiara la destinazione per intero")
check(mappa[0]["keywords"] == ["studio alfa", "cantiere"] and mappa[0]["title_only"] == ["sopralluogo"],
      "parole chiave portate in minuscolo")
check(brain_config.routing(make_vault()) == [], "brain.json assente → mappa vuota, nessun errore")
rc.ROUTING = mappa
put_call(root7, "2030-05-01-sopralluogo.md", fm("Sopralluogo di lunedì"))
res7 = rc.route(root7)
check(res7["routed"] == [("2030-05-01-sopralluogo.md", "studio-alfa")]
      and (root7 / "10-lavoro" / "clienti" / "studio-alfa" / "knowledge" / "calls"
           / "2030-05-01-sopralluogo.md").exists(),
      "il router smista con la mappa letta dal JSON")
rc.ROUTING = TEST_ROUTING

# ---------- cleanup + esito ----------
for r in vaults:
    shutil.rmtree(r, ignore_errors=True)

passed = sum(1 for ok, _ in results if ok)
total = len(results)
print(f"\n{passed}/{total} test passati")
sys.exit(0 if passed == total else 1)
