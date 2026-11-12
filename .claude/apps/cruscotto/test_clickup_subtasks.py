# 2nd Brain Hero Mode · Copyright (c) 2026 Alessandro Pacifico (Pacibrand).
# Vedi LICENZA.md nella radice del vault.
"""Test delle sottotask ClickUp nel cruscotto: l'API le restituisce in lista piatta col campo
`parent`, il cruscotto le deve rimettere sotto la madre. Nessuna chiamata a ClickUp: le due
letture sono sostituite.
    python3 .claude/apps/cruscotto/test_clickup_subtasks.py
"""
import importlib.util
import os
import sys
import tempfile
from pathlib import Path

os.environ["CLAUDE_PROJECT_DIR"] = tempfile.mkdtemp()    # server.py legge ROOT da qui

spec = importlib.util.spec_from_file_location("srv", str(Path(__file__).with_name("server.py")))
srv = importlib.util.module_from_spec(spec)
sys.modules["srv"] = srv
spec.loader.exec_module(srv)

fails = []


def chk(name, cond, extra=""):
    print(("  \033[32m✓\033[0m " if cond else "  \033[31m✗\033[0m ") + name
          + ("" if cond else f"\n      → {extra!r}"))
    if not cond:
        fails.append(name)


def raw(i, name, parent=None, status="open", typ="open", created=0):
    return {"id": i, "name": name, "parent": parent, "date_created": str(created),
            "status": {"status": status, "type": typ}, "list": {"id": "L"}}


chiamate = []                                            # madri per cui si sono chieste le chiuse


def vista(aperte, chiuse=None, rotto=False):
    """Fa girare clickup_live_tasks su una lista finta. `chiuse` = {id madre: [task grezze]}."""
    chiamate.clear()
    srv._LIVE_CACHE.update(t=0.0, data=None)
    srv.MEMBER_ID = "1"                                  # utente noto: nessuna domanda a ClickUp
    srv.WORKSPACES = [("T", None)]
    srv.EXCLUDE_STATUS = {"done", "complete", "closed", "idee"}
    srv._clickup_team_tasks = lambda _team: aperte

    def get(url):
        pid = url.split("parent=")[1].split("&")[0]
        chiamate.append(pid)
        return None if rotto else {"tasks": (chiuse or {}).get(pid, [])}
    srv.clickup_get = get
    return srv.clickup_live_tasks()


def nomi(tasks):
    return [t["text"] for t in tasks]


print("madre con quattro sottotask (API in ordine inverso rispetto alla creazione)")
piatta = [raw("s4", "Quarto passo", "m", created=4), raw("s3", "Terzo passo", "m", created=3),
          raw("s2", "Secondo passo", "m", created=2), raw("s1", "Primo passo", "m", created=1),
          raw("m", "Lancio campagna", created=0), raw("x", "Altra task", created=9)]
out = vista(piatta)
chk("due card, non sei", nomi(out) == ["Lancio campagna", "Altra task"], nomi(out))
madre = out[0]
chk("le quattro stanno sotto la madre, in ordine di creazione",
    nomi(madre["children"]) == ["Primo passo", "Secondo passo", "Terzo passo", "Quarto passo"],
    nomi(madre["children"]))
chk("sottotask spuntabili: fonte e id ClickUp al loro posto",
    all(c["source"] == "clickup" and c["cu_id"] and c["done"] is False for c in madre["children"]))
chk("le chiuse si chiedono solo per la madre che ha figlie", chiamate == ["m"], chiamate)

print("sottotask già chiuse")
out = vista(piatta, chiuse={"m": [raw("s0", "Passo zero", "m", "done", "done", created=-1),
                                  raw("s1", "Primo passo", "m", "done", "done", created=1),
                                  raw("s9", "Bozza", "m", "idee", "open", created=5)]})
kids = out[0]["children"]
chk("la chiusa entra come fatta, in testa per data", kids[0]["text"] == "Passo zero" and kids[0]["done"], nomi(kids))
chk("conteggio 1 su 5", (sum(k["done"] for k in kids), len(kids)) == (1, 5), nomi(kids))
chk("nessun doppione se una aperta ricompare fra le chiuse", nomi(kids).count("Primo passo") == 1)
chk("uno stato non chiuso non passa per fatto", "Bozza" not in nomi(kids), nomi(kids))

print("lettura delle chiuse fallita")
out = vista(piatta, rotto=True)
chk("restano le aperte, nessun errore", len(out[0]["children"]) == 4)

print("madre fuori lista")
out = vista([raw("s1", "Sottotask orfana", "altrove"), raw("x", "Altra task")])
chk("la sottotask resta una card a sé", nomi(out) == ["Sottotask orfana", "Altra task"], nomi(out))
chk("nessuna lettura in più", chiamate == [], chiamate)

print("sottotask di una sottotask")
out = vista([raw("n", "Nipote", "s1", created=2), raw("s1", "Figlia", "m", created=1), raw("m", "Madre")])
chk("una sola card", nomi(out) == ["Madre"], nomi(out))
chk("figlia e nipote sotto la madre di primo livello", nomi(out[0]["children"]) == ["Figlia", "Nipote"],
    nomi(out[0]["children"]))

print("stato escluso")
out = vista([raw("s1", "Idea", "m", status="idee"), raw("s2", "Vera", "m"), raw("m", "Madre")])
chk("la sottotask in uno stato escluso non compare", nomi(out[0]["children"]) == ["Vera"], nomi(out[0]["children"]))

print("\n" + ("\033[31mFALLITI: " + ", ".join(fails) + "\033[0m" if fails
              else "\033[32mTUTTI I TEST PASSATI\033[0m"))
sys.exit(1 if fails else 0)
