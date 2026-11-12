# 2nd Brain Hero Mode · Copyright (c) 2026 Alessandro Pacifico (Pacibrand).
# Vedi LICENZA.md nella radice del vault.
"""Test delle scritture markdown del cruscotto (note + sottotask manuali dal dettaglio).

Gira su un vault FINTO in una temp dir: il vault vero non viene mai toccato.
    python3 .claude/apps/cruscotto/test_note_subtask.py
"""
import importlib.util
import os
import sys
import tempfile
from pathlib import Path

TMP = Path(tempfile.mkdtemp())
os.environ["CLAUDE_PROJECT_DIR"] = str(TMP)          # server.py legge ROOT da qui

spec = importlib.util.spec_from_file_location("srv", str(Path(__file__).with_name("server.py")))
srv = importlib.util.module_from_spec(spec)
sys.modules["srv"] = srv
spec.loader.exec_module(srv)

REL = "proj/tasks/t.md"
F = TMP / REL
F.parent.mkdir(parents=True)
ORIG = """# Task

- [ ] Task madre 📅 2030-01-15 ⏫ #esempio
    - [ ] Prima figlia
    - [x] Seconda figlia

- [ ] Altra task #esempio
"""
fails = []


def chk(name, cond, extra=""):
    print(("  \033[32m✓\033[0m " if cond else "  \033[31m✗\033[0m ") + name
          + ("" if cond else f"\n      → {extra!r}"))
    if not cond:
        fails.append(name)


def reset():
    F.write_text(ORIG, encoding="utf-8")


def top(i=0):
    return srv.parse_file(F)[i]


print("\n[1] parse: struttura di partenza")
reset()
t = top()
chk("madre trovata", t["text"] == "Task madre", t["text"])
chk("2 figlie", len(t["children"]) == 2, len(t["children"]))
chk("nota vuota all'inizio", t["note"] == "", t["note"])
chk("riga corretta", t["line"] == 2, t["line"])

print("\n[2] nota multi-riga")
ok, msg = srv.native_set_note(REL, t["line"], t["text"], "Prima riga\nSeconda riga")
chk("write ok", ok, msg)
t = top()
chk("nota riletta", t["note"] == "Prima riga\nSeconda riga", t["note"])
chk("figlie intatte", len(t["children"]) == 2, len(t["children"]))
chk("scritta subito sotto la madre", F.read_text().splitlines()[3] == "    > Prima riga",
    F.read_text().splitlines()[3])
chk("figlie slittate di 2 righe", t["children"][0]["line"] == 5, t["children"][0]["line"])

print("\n[3] sostituzione: non deve accumulare")
srv.native_set_note(REL, top()["line"], "Task madre", "Sola riga")
t = top()
chk("sostituita, non appesa", t["note"] == "Sola riga", t["note"])
chk("una sola riga '>'", F.read_text().count("\n    > ") == 1, F.read_text())

print("\n[4] nota vuota = blocco rimosso")
srv.native_set_note(REL, top()["line"], "Task madre", "   ")
t = top()
chk("nota azzerata", t["note"] == "", t["note"])
chk("nessuna riga '>' residua", ">" not in F.read_text(), F.read_text())
chk("figlie ancora 2", len(t["children"]) == 2, len(t["children"]))

print("\n[5] sottotask: va in fondo al blocco, non sotto la task successiva")
reset()
ok, msg = srv.native_add_subtask(REL, top()["line"], "Task madre", "Terza figlia")
chk("write ok", ok, msg)
t = top()
chk("3 figlie", len(t["children"]) == 3, len(t["children"]))
chk("in coda", t["children"][-1]["text"] == "Terza figlia", t["children"][-1]["text"])
chk("'Altra task' resta senza figlie", len(top(1)["children"]) == 0, top(1)["children"])
chk("rientro a 4 spazi", F.read_text().splitlines()[5] == "    - [ ] Terza figlia",
    F.read_text().splitlines()[5])

print("\n[6] nota + sottotask insieme")
reset()
srv.native_set_note(REL, top()["line"], "Task madre", "Contesto")
srv.native_add_subtask(REL, top()["line"], "Task madre", "Ultima")
t = top()
chk("nota preservata", t["note"] == "Contesto", t["note"])
chk("3 figlie", len(t["children"]) == 3, len(t["children"]))
chk("ordine giusto", t["children"][-1]["text"] == "Ultima", [c["text"] for c in t["children"]])

print("\n[7] task nuda (né figlie né note)")
F.write_text("- [ ] Sola #x\n", encoding="utf-8")
srv.native_add_subtask(REL, 0, "Sola", "Nuova")
chk("figlia creata", len(top()["children"]) == 1, top()["children"])
srv.native_set_note(REL, 0, "Sola", "n")
chk("nota e figlia convivono", top()["note"] == "n" and len(top()["children"]) == 1,
    (top()["note"], len(top()["children"])))

print("\n[8] difese")
reset()
ok, msg = srv.native_set_note(REL, 2, "Testo che non combacia", "x")
chk("riga stantia rifiutata", not ok, msg)
ok, msg = srv.native_add_subtask(REL, 999, None, "x")
chk("riga fuori range rifiutata", not ok, msg)
ok, msg = srv.native_set_note("../../../etc/passwd", 0, None, "x")
chk("path traversal rifiutato", not ok, msg)
(TMP / "proj" / "note.md").write_text("- [ ] x\n", encoding="utf-8")
ok, msg = srv.native_set_note("proj/note.md", 0, None, "x")
chk("file fuori da tasks/ rifiutato", not ok, msg)
ok, msg = srv.native_add_subtask(REL, 2, "Task madre", "   ")
chk("sottotask vuota rifiutata", not ok, msg)
chk("file invariato dopo i rifiuti", F.read_text() == ORIG, F.read_text())

print("\n[9] sidecar locale per le task non native")
cu = {"source": "clickup", "cu_id": "abc", "text": "T"}
ok, msg = srv.set_note(cu, "nota CU")
chk("salvata nel sidecar", ok, msg)
chk("sidecar sotto _local-only", "_local-only" in str(srv.NOTE_FILE), srv.NOTE_FILE)
chk("riletta", srv._load_notes().get(srv._note_key(cu)) == "nota CU", srv._load_notes())
chk("nessun markdown creato per ClickUp", not (TMP / "proj" / "tasks" / "t.md").read_text().count(">"))
srv.set_note(cu, "")
chk("vuota = rimossa", srv._load_notes() == {}, srv._load_notes())

print("\n" + ("\033[31mFALLITI: " + ", ".join(fails) + "\033[0m" if fails
              else "\033[32mTUTTI I TEST PASSATI\033[0m"))
sys.exit(1 if fails else 0)
