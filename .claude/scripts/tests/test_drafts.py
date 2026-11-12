# 2nd Brain Hero Mode · Copyright (c) 2026 Alessandro Pacifico (Pacibrand).
# Vedi LICENZA.md nella radice del vault.
"""
Smoke test del ciclo di vita bozze: scadenza >24h da nome-file, fallback mtime, dry-run,
aggiornamento riga Stato, active->sent non toccato. Vault finto in tmp.

    python3 .claude/scripts/tests/test_drafts.py
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))

import drafts as dr  # noqa: E402

OK, KO = "[OK ]", "[FAIL]"
results: list[tuple[bool, str]] = []
NOW = datetime(2030, 7, 9, 12, 0, 0)


def check(cond: bool, label: str) -> None:
    results.append((bool(cond), label))
    print(f"  {OK if cond else KO} {label}")


def make_vault() -> Path:
    root = Path(tempfile.mkdtemp(prefix="dr-test-"))
    for sub in ("active", "sent", "expired"):
        (root / "drafts" / sub).mkdir(parents=True)
    (root / ".claude" / "data" / "locks").mkdir(parents=True)
    return root


def put_draft(root: Path, name: str, stato: str = "active") -> Path:
    p = root / "drafts" / "active" / name
    p.write_text(f"**A:** x\n**Oggetto:** y\n\ncorpo\n\n**Stato:** {stato}\n", encoding="utf-8")
    return p


# ---------- 1. calcolo eta' dal nome ----------
print("\n[1] eta' dal nome file")
check(dr.draft_age_hours("2030-07-09-1100-x-y.md", NOW) == 1.0, "bozza di 1h fa -> 1.0h")
check(dr.draft_age_hours("2030-07-08-1200-x-y.md", NOW) == 24.0, "bozza di ieri -> 24.0h")
check(dr.draft_age_hours("nota-libera.md", NOW) is None, "nome non standard -> None (userà mtime)")

# ---------- 2. scadenza reale ----------
print("\n[2] scadenza >24h")
root = make_vault()
put_draft(root, "2030-07-09-1100-fresca.md")            # 1h -> resta
put_draft(root, "2030-07-08-1000-vecchia.md")           # 26h -> scade
moved = dr.expire_stale_drafts(root, now=NOW)
check(moved == ["2030-07-08-1000-vecchia.md"], "solo la vecchia (>24h) scade")
check(not (root / "drafts" / "active" / "2030-07-08-1000-vecchia.md").exists(), "la vecchia lascia active/")
check((root / "drafts" / "expired" / "2030-07-08-1000-vecchia.md").exists(), "la vecchia arriva in expired/")
check((root / "drafts" / "active" / "2030-07-09-1100-fresca.md").exists(), "la fresca resta in active/")

# ---------- 3. riga Stato aggiornata ----------
print("\n[3] Stato aggiornato nel file scaduto")
txt = (root / "drafts" / "expired" / "2030-07-08-1000-vecchia.md").read_text(encoding="utf-8")
check("**Stato:** expired" in txt, "la riga Stato diventa 'expired'")

# ---------- 4. dry-run non muove ----------
print("\n[4] dry-run (preview)")
root2 = make_vault()
put_draft(root2, "2030-07-01-0900-antica.md")           # molto vecchia
would = dr.expire_stale_drafts(root2, now=NOW, dry_run=True)
check(would == ["2030-07-01-0900-antica.md"], "dry-run elenca cosa scadrebbe")
check((root2 / "drafts" / "active" / "2030-07-01-0900-antica.md").exists(), "dry-run NON sposta il file")

# ---------- 5. soglia configurabile ----------
print("\n[5] soglia personalizzata")
root3 = make_vault()
put_draft(root3, "2030-07-09-1000-due-ore.md")          # 2h
m = dr.expire_stale_drafts(root3, now=NOW, max_age_hours=1)  # soglia 1h
check(m == ["2030-07-09-1000-due-ore.md"], "con soglia 1h, una bozza di 2h scade")

# ---------- 6. active->sent non e' compito nostro ----------
print("\n[6] sent/ non toccato")
root4 = make_vault()
(root4 / "drafts" / "sent" / "gia-inviata.md").write_text("**Stato:** sent\n", encoding="utf-8")
dr.expire_stale_drafts(root4, now=NOW)
check((root4 / "drafts" / "sent" / "gia-inviata.md").exists(), "le bozze in sent/ restano dove sono")

# ---------- cleanup + esito ----------
for r in (root, root2, root3, root4):
    shutil.rmtree(r, ignore_errors=True)

passed = sum(1 for ok, _ in results if ok)
total = len(results)
print(f"\n{passed}/{total} test passati")
sys.exit(0 if passed == total else 1)
