# 2nd Brain Hero Mode · Copyright (c) 2026 Alessandro Pacifico (Pacibrand).
# Vedi LICENZA.md nella radice del vault.
"""
Test di health_check.py su vault finti in una cartella temporanea (nessuna rete).

    python3 .claude/scripts/tests/test_health_check.py

Copre cio' che cambia da una persona all'altra: l'autore dei commit (da brain.json, altrimenti
da git), la mappa dello smistamento letta dalla configurazione, e il silenzio dei controlli
quando il modulo non c'e' (nessun repository, nessun remote, giro orario mai installato).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))

import health_check as hc  # noqa: E402

results: list[tuple[bool, str]] = []


def check(cond: bool, label: str) -> None:
    results.append((bool(cond), label))
    print(f"  {'[OK ]' if cond else '[FAIL]'} {label}")


def git(cwd: Path, *args: str) -> None:
    subprocess.run(("git", *args), cwd=str(cwd), check=True, capture_output=True, text=True)


def vault(tmp: Path, name: str, config: dict | None = None) -> Path:
    """Un vault finto e, se serve, il suo brain.json."""
    root = tmp / name
    (root / ".claude" / "scripts").mkdir(parents=True)
    if config is not None:
        (root / ".claude" / "config").mkdir(parents=True)
        (root / ".claude" / "config" / "brain.json").write_text(json.dumps(config), encoding="utf-8")
    return root


def repo(root: Path, author: str) -> None:
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "t@t.t")
    git(root, "config", "user.name", author)
    (root / "a.md").write_text("base\n", encoding="utf-8")
    git(root, "add", "a.md")
    git(root, "commit", "-q", "-m", "base")


def esito(root: Path, controllo) -> tuple[str, str]:
    stato, _, dettaglio = controllo(root)
    return stato, dettaglio


tmp = Path(tempfile.mkdtemp(prefix="health-test-"))

print("\n[1] vault appena creato, senza git e senza moduli: nessun allarme")
vuoto = vault(tmp, "vuoto")
esiti = hc.esegui(vuoto)
check(all(s == hc.OK for s, _, _ in esiti), "tutti i controlli OK su un vault vuoto")
check(hc.render(esiti, solo_allarmi=True) == "", "--solo-allarmi non stampa nulla")
check("non e' un repository git" in esito(vuoto, hc.check_push)[1], "push: dice che non si applica")

print("\n[2] repository senza remote: il push non si applica, il backup si misura")
solo = vault(tmp, "solo")
repo(solo, "Mario Rossi")
check(esito(solo, hc.check_push) == (hc.OK, "nessun remote: il vault e' salvato solo su questo computer"),
      "push: nessun remote, nessun allarme")
check(esito(solo, hc.check_backup)[0] == hc.OK, "backup: trova il commit con il nome preso da git")

print("\n[3] autore dei commit dalla configurazione")
giusto = vault(tmp, "giusto", {"git_author": "Mario Rossi"})
repo(giusto, "Mario Rossi")
check(esito(giusto, hc.check_backup)[0] == hc.OK, "git_author uguale a chi firma: OK")
altro = vault(tmp, "altro", {"git_author": "Qualcun Altro"})
repo(altro, "Mario Rossi")
stato, dettaglio = esito(altro, hc.check_backup)
check(stato == hc.ALLARME and "Qualcun Altro" in dettaglio and "brain.json" in dettaglio,
      "git_author che non firma nessun commit: allarme che dice dove correggere")

print("\n[4] repository con remote: allineato, poi con una pila di commit non spinti")
origin = tmp / "origin.git"
subprocess.run(("git", "init", "-q", "--bare", "-b", "main", str(origin)), check=True, capture_output=True)
git(solo, "remote", "add", "origin", str(origin))
check(esito(solo, hc.check_push)[0] == hc.ALLARME, "remote collegato ma primo push mai fatto: allarme")
git(solo, "push", "-q", "origin", "main")
check(esito(solo, hc.check_push) == (hc.OK, "allineato con origin"), "dopo il push: allineato")
for i in range(hc.MAX_COMMIT_NON_PUSHATI + 1):
    (solo / f"f{i}.md").write_text("x\n", encoding="utf-8")
    git(solo, "add", "-A")
    git(solo, "commit", "-q", "-m", f"c{i}")
check(esito(solo, hc.check_push)[0] == hc.ALLARME, "troppi commit non spinti: allarme")

print("\n[5] smistamento: la mappa viene dalla configurazione")
cfg = {"projects": [{"id": "progetto-esempio", "path": "10-lavoro/progetto-esempio", "keywords": []}]}
mappa = vault(tmp, "mappa", cfg)
check("non installato" in esito(mappa, hc.check_router)[1], "senza route_calls.py: non si applica")
(mappa / ".claude" / "scripts" / "route_calls.py").write_text("# smistamento\n", encoding="utf-8")
calls = mappa / "10-lavoro" / "progetto-esempio" / "knowledge" / "calls"
calls.mkdir(parents=True)
(calls / "2030-01-10-call-esempio.md").write_text("x", encoding="utf-8")
check(esito(mappa, hc.check_router)[0] == hc.OK, "progetto con call e presente in brain.json: OK")
fuori = mappa / "10-lavoro" / "progetto-nuovo" / "knowledge" / "calls"
fuori.mkdir(parents=True)
(fuori / "2030-01-11-call-esempio.md").write_text("x", encoding="utf-8")
stato, dettaglio = esito(mappa, hc.check_router)
check(stato == hc.ALLARME and "progetto-nuovo" in dettaglio and "progetto-esempio" not in dettaglio,
      "progetto con call ma fuori dalla mappa: allarme col suo nome")

print("\n[6] giro orario: non installato tace, fermo da giorni suona")
check(esito(mappa, hc.check_giro_orario)[0] == hc.OK, "nessun log del giro: non si applica")
(mappa / ".claude" / "data").mkdir(parents=True)
(mappa / ".claude" / "data" / "autopilot.log").write_text("[2000-01-01 08:00] backup: exit 0\n", encoding="utf-8")
check(esito(mappa, hc.check_giro_orario)[0] == hc.ALLARME, "ultimo giro vecchissimo: allarme")

print("\n[7] tetti per file delle fonti di sessione")
(mappa / "02-memoria").mkdir()
(mappa / "02-memoria" / "me.md").write_text("x" * int(hc.BUDGET_FILE["02-memoria/me.md"] * 0.9), encoding="utf-8")
stato, dettaglio = esito(mappa, hc.check_budget_file)
check(stato == hc.ALLARME and "02-memoria/me.md" in dettaglio, "me.md oltre l'80% del suo tetto: allarme")

print("\n[8] metodo ed essenziali di progetto: avviso all'80% del tetto")
import os  # noqa: E402

check(esito(vuoto, hc.check_essenziali_progetti)[0] == hc.OK, "senza hook del contesto: non si applica")
ess = vault(tmp, "essenziali", {"projects": [{"id": "alfa", "path": "10-lavoro/alfa"}]})
(ess / ".claude" / "hooks").mkdir()
shutil.copy2(SCRIPTS.parent / "hooks" / "project-context.py", ess / ".claude" / "hooks" / "project-context.py")
shutil.copy2(SCRIPTS / "brain_config.py", ess / ".claude" / "scripts" / "brain_config.py")
ref = ess / "10-lavoro" / "alfa" / "references"
ref.mkdir(parents=True)
(ref / "metodo.md").write_text("# Metodo\npoche righe\n", encoding="utf-8")
vecchia = os.environ.get("CLAUDE_PROJECT_DIR")
os.environ["CLAUDE_PROJECT_DIR"] = str(ess)
try:
    stato, dettaglio = esito(ess, hc.check_essenziali_progetti)
    check(stato == hc.OK and "sotto l'80%" in dettaglio, "metodo corto: tutto a posto")
    (ref / "metodo.md").write_text("x" * 11000, encoding="utf-8")
    (ref / "brand.md").write_text("y" * 14000, encoding="utf-8")
    stato, dettaglio = esito(ess, hc.check_essenziali_progetti)
    check(stato == hc.ALLARME and "alfa metodo" in dettaglio and "alfa essenziali" in dettaglio,
          "metodo ed essenziali oltre l'80%: allarme con il nome del progetto")
finally:
    if vecchia is None:
        os.environ.pop("CLAUDE_PROJECT_DIR", None)
    else:
        os.environ["CLAUDE_PROJECT_DIR"] = vecchia

shutil.rmtree(tmp, ignore_errors=True)
passed = sum(1 for ok, _ in results if ok)
print(f"\n{passed}/{len(results)} test passati")
sys.exit(0 if passed == len(results) else 1)
