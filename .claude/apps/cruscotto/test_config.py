# 2nd Brain Hero Mode · Copyright (c) 2026 Alessandro Pacifico (Pacibrand).
# Vedi LICENZA.md nella radice del vault.
"""Test della configurazione del cruscotto. Con brain.json assente o vuoto la board serve le sole
task native del vault, senza nessuna chiamata a ClickUp né ad Apple; con brain.json compilato i
valori arrivano dove servono; un brain.json scritto male non fa cadere nulla.

Vault finto in una temp dir. Rete e osascript sono sostituiti da trappole: se il codice li
chiamasse, il test lo vedrebbe.
    python3 .claude/apps/cruscotto/test_config.py
"""
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

TMP = Path(tempfile.mkdtemp())
os.environ["CLAUDE_PROJECT_DIR"] = str(TMP)              # server.py legge ROOT da qui

TASKS = TMP / "10-lavoro" / "progetto-esempio" / "tasks" / "aperti.md"
TASKS.parent.mkdir(parents=True)
TASKS.write_text("- [ ] Prima task di prova 📅 2030-01-15 ⏫\n- [ ] Seconda task di prova #urgente\n",
                 encoding="utf-8")

spec = importlib.util.spec_from_file_location("srv", str(Path(__file__).with_name("server.py")))
srv = importlib.util.module_from_spec(spec)
sys.modules["srv"] = srv
spec.loader.exec_module(srv)

fails = []
fuori = []                                               # ogni tentativo di uscire dal processo finisce qui


def chk(name, cond, extra=""):
    print(("  \033[32m✓\033[0m " if cond else "  \033[31m✗\033[0m ") + name
          + ("" if cond else f"\n      → {extra!r}"))
    if not cond:
        fails.append(name)


def _trappola(nome):
    def scatta(*a, **_k):
        fuori.append((nome, a[0] if a else None))
        raise RuntimeError(f"{nome}: chiamata esterna non ammessa nel test")
    return scatta


srv.urllib.request.urlopen = _trappola("rete")
srv.subprocess.run = _trappola("osascript")


def scrivi(cfg):
    p = TMP / ".claude" / "config" / "brain.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(cfg if isinstance(cfg, str) else json.dumps(cfg), encoding="utf-8")
    srv._LIVE_CACHE.update(t=0.0, data=None)
    srv._DELEGATED_CACHE.update(t=0.0, data=None)
    srv._CU_STATE.update(err=None, member=None)
    srv.apply_config()


print("brain.json assente: solo le task del vault")
p = srv.board_payload()
chk("le due task native ci sono", [t["text"] for t in p["tasks"]] == ["Prima task di prova", "Seconda task di prova"],
    [t["text"] for t in p["tasks"]])
chk("tutte di fonte vault", all(t["source"] == "native" for t in p["tasks"]))
chk("data e priorità lette", (p["tasks"][0]["due"], p["tasks"][0]["prio"]) == ("2030-01-15", "high"), p["tasks"][0])
chk("ClickUp spento, detto in una riga", p["clickup"] == {"on": False, "mentions": False, "delegated": False,
                                                          "msg": "ClickUp non configurato"}, p["clickup"])
chk("nessun workspace, nessuna lista", (srv.WORKSPACES, srv.DELEGATED_LISTS, srv.MENTION_SCOPES) == ([], [], []))
chk("menzioni e delegate vuote", srv.mentions() == [] and srv.delegated_tasks() == [])
chk("il giro delle menzioni non parte", srv._mentions_loop() is None)
chk("nessun banner promemoria", p["reminders"]["ok"] and p["reminders"]["err"] is None, p["reminders"])
chk("porta di default", srv.PORT == 8765, srv.PORT)
chk("calendario spento", srv.CAL_ON is False)
chk("nessuna chiamata esterna", fuori == [], fuori)

print("brain.json con un progetto e Promemoria spento")
scrivi({"projects": [{"id": "Progetto-Esempio", "path": "10-lavoro/progetto-esempio"}],
        "cruscotto": {"port": 8811, "reminders": False}})
p = srv.board_payload()
chk("porta da brain.json", srv.PORT == 8811, srv.PORT)
chk("promemoria spento e senza avviso", p["reminders"]["enabled"] is False and p["reminders"]["ok"], p["reminders"])
chk("progetto per filtri e colori", p["projects"] == [{"id": "Progetto-Esempio", "path": "10-lavoro/progetto-esempio",
                                                       "tag": "progetto-esempio"}], p["projects"])
chk("una sola destinazione: il file task del progetto",
    p["targets"] == [{"key": "vault-Progetto-Esempio", "label": "Vault · Progetto-Esempio", "kind": "native",
                      "tag": "progetto-esempio"}], p["targets"])
ok, msg = srv.create_task("vault-Progetto-Esempio", "Creata dal test", "2030-02-01", ["Sotto"], ["progetto-esempio"])
chk("aggiunta rapida nel file del progetto", ok and TASKS.read_text(encoding="utf-8").endswith(
    "- [ ] Creata dal test 📅 2030-02-01 #progetto-esempio\n    - [ ] Sotto\n"), (msg, TASKS.read_text(encoding="utf-8")))
ok, msg = srv.create_task("reminder", "Non deve partire", None)
chk("destinazione Promemoria non ammessa a modulo spento", not ok, msg)
chk("ancora nessuna chiamata esterna", fuori == [], fuori)

print("ClickUp compilato")
(TMP / "_local-only" / "secrets").mkdir(parents=True)
(TMP / "_local-only" / "secrets" / ".env").write_text("# finta\nCLICKUP_TOKEN=chiave-finta\n", encoding="utf-8")
scrivi({"reminders_list": "Lavoro", "cruscotto": {"reminders": False},
        "clickup": {"member_id": "", "exclude_statuses": ["Idee"],
                    "workspaces": [{"id": 111, "tag": "Team Uno"}, {"id": "222", "lists": ["L1"]}],
                    "quick_add": {"_leggimi": "nota", "Generale": "L1"},
                    "delegated_lists": ["L1", 22],
                    "mention_scopes": [{"workspace": "111"}, {"workspace": "222", "spaces": ["S1", "S2"]}]}})
chk("workspace e filtro lista", srv.WORKSPACES == [("111", None), ("222", frozenset({"L1"}))], srv.WORKSPACES)
chk("tag per workspace, con default", srv.WS_TAG == {"111": "teamuno", "222": "clickup"}, srv.WS_TAG)
chk("stati esclusi in minuscolo", srv.EXCLUDE_STATUS == {"idee"}, srv.EXCLUDE_STATUS)
chk("liste delegate come stringhe", srv.DELEGATED_LISTS == ["L1", "22"], srv.DELEGATED_LISTS)
chk("ambiti delle menzioni", srv.MENTION_SCOPES == [("111", ""), ("222", "&space_ids[]=S1&space_ids[]=S2")],
    srv.MENTION_SCOPES)
chk("aggiunta rapida: la nota non diventa una lista",
    {k: v["label"] for k, v in srv.CREATE_TARGETS.items()} == {"clickup-L1": "ClickUp · Generale"}, srv.CREATE_TARGETS)

chieste = []


def finta_api(url):
    chieste.append(url)
    if url.endswith("/user"):
        return {"user": {"id": 77}}
    if "/team/111/" in url:
        return {"last_page": True, "tasks": [
            {"id": "a", "name": "Senza tag", "status": {"status": "open"}, "list": {"id": "L9"}, "tags": []},
            {"id": "b", "name": "In uno stato escluso", "status": {"status": "Idee"}, "list": {"id": "L9"}}]}
    if "/team/222/" in url:
        return {"last_page": True, "tasks": [
            {"id": "c", "name": "Nella lista ammessa", "status": {"status": "open"}, "list": {"id": "L1"},
             "tags": [{"name": "suo-tag"}]},
            {"id": "d", "name": "In un'altra lista", "status": {"status": "open"}, "list": {"id": "L2"}}]}
    return None


srv.clickup_get = finta_api
p = srv.board_payload()
cu = {t["text"]: t for t in p["tasks"] if t["source"] == "clickup"}
chk("entrano solo le task ammesse", sorted(cu) == ["Nella lista ammessa", "Senza tag"], sorted(cu))
chk("la task senza tag prende il tag del workspace", cu["Senza tag"]["tags"] == ["teamuno"], cu["Senza tag"]["tags"])
chk("la task con un suo tag lo tiene", cu["Nella lista ammessa"]["tags"] == ["suo-tag"])
chk("l'id utente si chiede una volta sola", sum(u.endswith("/user") for u in chieste) == 1, chieste)
chk("e finisce nel filtro delle letture", all("assignees[]=77" in u for u in chieste if "/team/" in u), chieste)
chk("le task del vault restano", sum(t["source"] == "native" for t in p["tasks"]) == 3, len(p["tasks"]))
chk("stato: connesso, con menzioni e delegate", p["clickup"] == {"on": True, "mentions": True, "delegated": True,
                                                                 "msg": "connesso a ClickUp"}, p["clickup"])
srv._CU_STATE["err"] = "HTTP Error 401: Unauthorized"
chk("una chiave rifiutata si vede a piè di pagina", "non raggiungibile" in srv.clickup_status()["msg"],
    srv.clickup_status())

print("brain.json scritto male")
for nome, cfg in [("sezioni del tipo sbagliato", {"clickup": "boh", "cruscotto": [], "projects": "x", "reminders_list": 3}),
                  ("valori del tipo sbagliato", {"clickup": {"workspaces": "111", "quick_add": ["L1"],
                                                             "mention_scopes": {"a": 1}, "delegated_lists": 5},
                                                 "cruscotto": {"port": "abc"}}),
                  ("file che non è JSON", "{ non è json")]:
    try:
        scrivi(cfg)
        srv.clickup_get = lambda _u: None
        srv.board_payload()
        esito = True
    except Exception as e:                               # qualunque eccezione è un fallimento del test
        esito = repr(e)
    chk(f"{nome}: nessun errore", esito is True, esito)
chk("porta non valida: resta quella di default", srv.PORT == 8765, srv.PORT)
chk("mai una chiamata esterna vera in tutto il test", fuori == [], fuori)

print("\n" + ("\033[31mFALLITI: " + ", ".join(fails) + "\033[0m" if fails
              else "\033[32mTUTTI I TEST PASSATI\033[0m"))
sys.exit(1 if fails else 0)
