# 2nd Brain Hero Mode · Copyright (c) 2026 Alessandro Pacifico (Pacibrand).
# Vedi LICENZA.md nella radice del vault.
"""
Test di sync_with_remote (hook SessionStart). Due repo git veri in tmp, nessuna rete.

    python3 .claude/scripts/tests/test_session_sync.py

Copre il caso dei due scrittori: il Mac e la routine notturna scrivono entrambi, il push
orario viene rifiutato non-fast-forward e il vault resta fuori da GitHub in silenzio.
Copre anche il vault senza GitHub (nessun repo, o repo senza remote): l'hook deve tacere.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HOOKS = Path(__file__).resolve().parent.parent.parent / "hooks"
spec = importlib.util.spec_from_file_location("ssc", HOOKS / "session-start-context.py")
ssc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ssc)

OK, KO = "[OK ]", "[FAIL]"
results: list[tuple[bool, str]] = []


def check(cond: bool, label: str) -> None:
    results.append((bool(cond), label))
    print(f"  {OK if cond else KO} {label}")


def git(cwd: Path, *args: str) -> None:
    subprocess.run(("git", *args), cwd=str(cwd), check=True,
                   capture_output=True, text=True)


def make_pair() -> tuple[Path, Path]:
    """Crea un 'origin' bare + un clone locale, come il vault e GitHub."""
    tmp = Path(tempfile.mkdtemp(prefix="sync-test-"))
    origin, work = tmp / "origin.git", tmp / "work"
    subprocess.run(("git", "init", "--bare", "-b", "main", str(origin)),
                   check=True, capture_output=True)
    subprocess.run(("git", "clone", str(origin), str(work)), check=True, capture_output=True)
    git(work, "config", "user.email", "t@t.t")
    git(work, "config", "user.name", "t")
    (work / "a.md").write_text("base\n", encoding="utf-8")
    git(work, "add", "-A")
    git(work, "commit", "-m", "base")
    git(work, "push", "-q", "origin", "main")
    return origin, work


def other_clone(origin: Path, name: str) -> Path:
    """Il 'secondo scrittore': la routine notturna che pusha mentre il Mac dorme."""
    d = origin.parent / name
    subprocess.run(("git", "clone", str(origin), str(d)), check=True, capture_output=True)
    git(d, "config", "user.email", "n@n.n")
    git(d, "config", "user.name", "notturna")
    return d


def commit(repo: Path, fname: str, text: str) -> None:
    (repo / fname).write_text(text, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-m", f"c-{fname}")


roots: list[Path] = []

# ---------- 1. in pari → silenzio ----------
print("\n[1] in pari con origin → nessun rumore")
origin, work = make_pair(); roots.append(origin.parent)
check(ssc.sync_with_remote(work) == "", "vault allineato → stringa vuota (niente da dire)")

# ---------- 2. indietro → fast-forward e lo dice ----------
print("\n[2] indietro (ha scritto solo la notturna) → si allinea")
night = other_clone(origin, "night")
commit(night, "b.md", "lavoro notturno\n")
git(night, "push", "-q", "origin", "main")
out = ssc.sync_with_remote(work)
check("allineato" in out and "1 commit" in out, "riporta di aver tirato giu' 1 commit")
check((work / "b.md").exists(), "il file della notturna e' ORA nel working tree")

# ---------- 3. divergenti → NON fonde, avvisa ----------
print("\n[3] divergenti (hanno scritto entrambi) → non fonde da sola")
commit(night, "c.md", "altra notte\n")
git(night, "push", "-q", "origin", "main")
commit(work, "d.md", "lavoro locale\n")          # stesso punto di partenza → divergenza
out = ssc.sync_with_remote(work)
check("DIVERGENTI" in out, "segnala la divergenza invece di fondere")
check(not (work / "c.md").exists(), "NON ha fuso: il file remoto non e' stato tirato dentro")
check("backup orario continua a fallire" in out,
      "spiega la conseguenza vera (il vault non e' su GitHub)")

# ---------- 4. solo avanti → nota, non allarme ----------
print("\n[4] solo avanti → nota tranquilla")
origin2, work2 = make_pair(); roots.append(origin2.parent)
commit(work2, "e.md", "solo locale\n")
out = ssc.sync_with_remote(work2)
check("non ancora su GitHub" in out, "dice che ci sono commit locali da pushare")
check("DIVERGENTI" not in out, "non grida alla divergenza quando non c'e'")

# ---------- 5. niente rete / non un repo → non rompe la sessione ----------
print("\n[5] robustezza: mai far fallire l'avvio")
nowhere = Path(tempfile.mkdtemp(prefix="sync-norepo-")); roots.append(nowhere)
check(ssc.sync_with_remote(nowhere) == "", "cartella che non e' un repo git → stringa vuota")
check(ssc.unmerged_cloud_branches(nowhere) == "", "cartella che non e' un repo git → nessun avviso cloud")

# ---------- 6. repo git senza remote (GitHub non ancora collegato) → silenzio ----------
print("\n[6] repo git senza remote → nessun rumore")
solo = Path(tempfile.mkdtemp(prefix="sync-noremote-")); roots.append(solo)
subprocess.run(("git", "init", "-q", "-b", "main", str(solo)), check=True, capture_output=True)
git(solo, "config", "user.email", "t@t.t")
git(solo, "config", "user.name", "t")
commit(solo, "a.md", "solo locale, senza GitHub\n")
check(ssc.sync_with_remote(solo) == "", "repo senza remote → stringa vuota")
check(ssc.unmerged_cloud_branches(solo) == "", "repo senza remote → nessun avviso cloud")

# ---------- 7. vault appena creato: il contesto si costruisce comunque ----------
print("\n[7] vault vuoto → contesto minimo, nessun errore")
import os  # noqa: E402
vuoto = Path(tempfile.mkdtemp(prefix="sync-vuoto-")); roots.append(vuoto)
os.environ["CLAUDE_PROJECT_DIR"] = str(vuoto)
os.environ.pop("CLAUDE_INVOKED_BY", None)
ctx = ssc.build_context()
check("## Oggi" in ctx, "vault vuoto → c'e' almeno la data di oggi")
check("## Capisaldi" not in ctx and "## Chi e'" not in ctx and "Giro posta" not in ctx,
      "vault vuoto → i pezzi senza fonte tacciono")

# ---------- 8. coda memoria: si contano i candidati veri, non l'esempio di formato ----------
print("\n[8] coda memoria → l'esempio di formato non e' un candidato")
(vuoto / "02-memoria").mkdir()
coda = vuoto / "02-memoria" / "PROMOTE-QUEUE.md"
ESEMPIO = "### [AAAA-MM-GG] <tipo> → <destinazione>\n**Proposta:** <testo>\n"
coda.write_text("# Coda\n\n## In attesa\n\n" + ESEMPIO + "\n---\n\n## Promossi\n", encoding="utf-8")
check(ssc.count_promote_candidates(vuoto) == 0, "solo l'esempio → 0 candidati")
check("coda promote" not in ssc.build_context(), "coda vuota → nessuna riga sulla coda")
coda.write_text("# Coda\n\n## In attesa\n\n" + ESEMPIO + "\n### [2030-01-10] fatto → wiki globale\n"
                "**Proposta:** una cosa da ricordare\n\n---\n\n## Promossi\n\n### [2030-01-02] fatto\n",
                encoding="utf-8")
check(ssc.count_promote_candidates(vuoto) == 1, "un candidato vero in attesa → 1 (lo storico non conta)")
check("coda promote: 1 in attesa, il piu' vecchio dal 2030-01-10" in ssc.build_context(),
      "il contesto riporta la coda con la data del piu' vecchio")

for r in roots:
    shutil.rmtree(r, ignore_errors=True)

passed = sum(1 for ok, _ in results if ok)
print(f"\n{passed}/{len(results)} test passati")
sys.exit(0 if passed == len(results) else 1)
