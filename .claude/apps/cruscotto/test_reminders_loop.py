# 2nd Brain Hero Mode · Copyright (c) 2026 Alessandro Pacifico (Pacibrand).
# Vedi LICENZA.md nella radice del vault.
"""Test del giro promemoria del cruscotto: un ripiego che salta non ferma il giro, e un giro
fermo si vede nel banner. Nessuna chiamata ad Apple: pull e archivio sono sostituiti.
    python3 .claude/apps/cruscotto/test_reminders_loop.py
"""
import importlib.util
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ["CLAUDE_PROJECT_DIR"] = tempfile.mkdtemp()    # server.py legge ROOT da qui

spec = importlib.util.spec_from_file_location("srv", str(Path(__file__).with_name("server.py")))
srv = importlib.util.module_from_spec(spec)
sys.modules["srv"] = srv
spec.loader.exec_module(srv)

srv.REM_ON = True                                        # modulo acceso anche dove non c'è macOS
srv.REM_STORE_FALLBACK = True                            # il ripiego sull'archivio è il caso sotto esame

fails = []


def chk(name, cond, extra=""):
    print(("  \033[32m✓\033[0m " if cond else "  \033[31m✗\033[0m ") + name
          + ("" if cond else f"\n      → {extra!r}"))
    if not cond:
        fails.append(name)


class _Stop(BaseException):                              # esce dal while True senza passare dall'except
    pass


def _giri(n):
    """Fa girare _reminders_loop per n giri: la sleep finta conta e poi interrompe."""
    fatti = []

    def finta(_s):
        fatti.append(1)
        if len(fatti) >= n:
            raise _Stop()
    vera, srv.time.sleep = srv.time.sleep, finta
    try:
        srv._reminders_loop()
    except _Stop:
        pass
    finally:
        srv.time.sleep = vera
    return len(fatti)


def _rotto():
    raise ModuleNotFoundError("No module named 'sqlite3'")   # ciò che succede dopo un aggiornamento di Python


print("pull riuscito")
srv._reminders_pull_live = lambda: ([{"name": "A", "due": None}], None)
_giri(1)
st = srv.reminders_status()
chk("cache viva", srv._REM_CACHE["data"] == [{"name": "A", "due": None}] and st["mode"] == "live", st)
chk("nessun avviso", st["ok"], st)

print("pull fallito e ripiego che salta")
srv._reminders_pull_live = lambda: (None, "errore di prova")
srv._reminders_from_store = _rotto
chk("il giro continua", _giri(3) == 3)
st = srv.reminders_status()
chk("avviso acceso", not st["ok"] and st["err"], st)
chk("resta l'ultima fotografia buona", srv._REM_CACHE["data"] == [{"name": "A", "due": None}])

print("il pull torna")
srv._reminders_pull_live = lambda: ([{"name": "A", "due": None}, {"name": "B", "due": None}], None)
_giri(1)
st = srv.reminders_status()
chk("cache aggiornata", len(srv._REM_CACHE["data"]) == 2 and st["ok"], st)

print("giro fermo senza errore")
srv._REM_CACHE.update(t=time.time() - srv.REM_STALE_S - 1, err=None)
st = srv.reminders_status()
chk("avviso acceso anche senza errore", not st["ok"] and "fermato" in (st["err"] or ""), st)

print("\n" + ("\033[31mFALLITI: " + ", ".join(fails) + "\033[0m" if fails
              else "\033[32mTUTTI I TEST PASSATI\033[0m"))
sys.exit(1 if fails else 0)
