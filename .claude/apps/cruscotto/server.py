#!/usr/bin/env python3
# 2nd Brain Hero Mode · Copyright (c) 2026 Alessandro Pacifico (Pacibrand).
# Vedi LICENZA.md nella radice del vault.
"""Cruscotto: board locale delle task (web-app, solo questo computer).

Gira SOLO su 127.0.0.1 (localhost): i dati non escono dal computer. Mette in un'unica board
settimanale tre fonti: le task native del vault (`<progetto>/tasks/*.md`), ClickUp (via API) e
Apple Promemoria (via osascript, solo macOS). Una fonte non configurata si spegne da sola:
senza ClickUp e senza Promemoria restano le task del vault, e la board funziona uguale.

Tutto ciò che cambia da persona a persona sta in `.claude/config/brain.json` (vedi
`apply_config` più sotto). La chiave ClickUp si legge dal file `_local-only/secrets/.env`
(riga `CLICKUP_TOKEN=...`): mai dal codice, mai da una variabile d'ambiente.

Avvio:  python3 .claude/apps/cruscotto/server.py    →   http://127.0.0.1:8765
        (la porta è `cruscotto.port` in brain.json; `--url` stampa l'indirizzo ed esce)
Stop:   Ctrl+C
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[3])
STATIC = Path(__file__).resolve().parent / "static"

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import brain_config  # noqa: E402  (lettore di .claude/config/brain.json)

# --- Configurazione personale: tutto da brain.json, niente di cablato ---
# Valori di modulo riempiti da apply_config() (in fondo al file) quando il modulo viene caricato.
# Chi cambia brain.json deve riavviare il cruscotto.
HOST, PORT = "127.0.0.1", 8765
MEMBER_ID = ""               # id utente ClickUp; vuoto = chiesto una volta a ClickUp con la chiave
WORKSPACES = []              # [(id workspace, insieme di id lista ammessi oppure None = tutte)]
WS_TAG = {}                  # {id workspace: tag dato alle task che su ClickUp non hanno tag}
EXCLUDE_STATUS = set()       # stati ClickUp (in minuscolo) che non entrano in board
MENTION_SCOPES = []          # [(id workspace, filtro query)] dove cercare le menzioni; vuoto = spento
DELEGATED_LISTS = []         # id delle liste dove cercare le task delegate; vuoto = spento
CREATE_TARGETS = {}          # destinazioni dell'aggiunta rapida: chiave → {kind, label, ...}
PROJECTS = []                # progetti dichiarati: [{id, path, tag}] (filtri e colori del frontend)
REM_LIST = "Lavoro"          # la lista di Apple Promemoria mostrata in board (solo quella)
REM_ON = False               # Promemoria acceso: solo macOS, e solo se non spento in brain.json
REM_STORE_FALLBACK = False   # ripiego sull'archivio locale di Promemoria: solo se chiesto
CAL_ON = False               # Calendario acceso: solo macOS, solo se chiesto e se lo script esiste
CAL_NAMES = []               # calendari da leggere (campo `calendars`); vuoto = tutti

TASK_RE = re.compile(r"^\s*-\s*\[( |x|X)\]\s+(.*)$")
DUE_RE = re.compile(r"📅\s*(\d{4}-\d{2}-\d{2})")
CU_RE = re.compile(r"<!--\s*cu:(\S+)\s+ws:(\S+)\s+st:([^>]*?)\s*-->")
REM_RE = re.compile(r"<!--\s*rem-list:([^>]*?)\s*-->")
URL_RE = re.compile(r"\[CU\]\((https?://[^)]+)\)")
TAG_RE = re.compile(r"#([\w/-]+)")
DONE_RE = re.compile(r"✅\s*\d{4}-\d{2}-\d{2}")
PRIO = {"🔺": "highest", "⏫": "high", "🔼": "medium", "🔽": "low", "⏬": "lowest"}
NOTE_RE = re.compile(r"^(\s*)>\s?(.*)$")                     # riga-nota: `    > testo` sotto la task


def task_roots():
    base = ROOT / "03-task"
    roots = [base / "clickup-mirror", base / "reminders-mirror"]
    for p in ROOT.glob("*/**/tasks"):
        s = str(p)
        if p.is_dir() and "_TEMPLATE" not in s and ".obsidian" not in s and "/.claude/" not in s:
            roots.append(p)
    return roots


def clean(body: str) -> str:
    s = CU_RE.sub("", body)
    s = REM_RE.sub("", s)
    s = URL_RE.sub("", s)
    s = DUE_RE.sub("", s)
    s = DONE_RE.sub("", s)
    s = TAG_RE.sub("", s)
    s = s.replace("🔗", "")
    for e in PRIO:
        s = s.replace(e, "")
    s = re.sub(r"\*\*([^*]+)\*\*", r"\1", s)                  # **grassetto** → testo pulito
    s = re.sub(r"\[\[([^\]]+)\]\]", r"\1", s)                 # [[wikilink]] → nome
    return re.sub(r"\s+", " ", s).strip(" -·" + chr(0x2014))  # 0x2014 = trattino lungo ai bordi del testo


def parse_file(path: Path):
    out, stack = [], []                                      # stack = (indent, task) per annidare le sottotask
    note_owner = None                                        # task di cui stiamo leggendo il blocco-note
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return out
    for i, line in enumerate(lines):
        m = TASK_RE.match(line)
        if not m:
            nm = NOTE_RE.match(line)
            if nm and note_owner is not None:                # `> …` subito sotto la task = nota
                txt = nm.group(2).rstrip()
                note_owner["note"] = f"{note_owner['note']}\n{txt}" if note_owner["note"] else txt
            elif line.strip():
                note_owner = None                            # riga di altro tipo → il blocco-note è finito
            continue
        done = m.group(1).lower() == "x"
        indent = len(line) - len(line.lstrip())
        body = m.group(2)
        cu, rem = CU_RE.search(body), REM_RE.search(body)
        due = DUE_RE.search(body)
        url = URL_RE.search(body)
        prio = next((n for e, n in PRIO.items() if e in body), None)
        source = "clickup" if cu else "reminder" if rem else "native"
        task = {
            "text": clean(body),
            "due": due.group(1) if due else None,
            "prio": prio,
            "tags": TAG_RE.findall(body),
            "source": source,
            "cu_id": cu.group(1) if cu else None,
            "ws": cu.group(2) if cu else None,
            "url": url.group(1) if url else None,
            "file": str(path.relative_to(ROOT)),
            "line": i,
            "done": done,
            "note": "",
            "children": [],
        }
        while stack and stack[-1][0] >= indent:
            stack.pop()
        if stack:
            stack[-1][1]["children"].append(task)            # più indentata → sottotask del genitore
        elif not done:
            out.append(task)                                 # top-level: mostrata solo se non completata
        stack.append((indent, task))
        note_owner = task                                    # le `> …` che seguono sono note di QUESTA task
    return out


# --- ClickUp live (dati freschi via API, non solo dai mirror) ---
DONE_TYPES = {"done", "closed"}                              # status.type di ClickUp per una task chiusa
PRIO_MAP = {"urgent": "highest", "high": "high", "normal": None, "low": "low"}
_LIVE_CACHE = {"t": 0.0, "data": None}
_CU_STATE = {"err": None, "member": None}                    # ultimo errore dell'API · id utente scoperto


def member_id():
    """Id ClickUp dell'utente. Si legge da brain.json (`clickup.member_id`); se manca si chiede una
    volta a ClickUp chi è il titolare della chiave. Stringa vuota = sconosciuto: chi la riceve
    non fa partire nessuna lettura (senza filtro arriverebbero le task di tutto il workspace)."""
    if MEMBER_ID:
        return MEMBER_ID
    if _CU_STATE["member"] is None:
        uid = ((clickup_get("https://api.clickup.com/api/v2/user") or {}).get("user") or {}).get("id")
        if uid:
            _CU_STATE["member"] = str(uid)
    return _CU_STATE["member"] or ""


def _clickup_team_tasks(team_id):
    me = member_id()
    if not me:
        return []
    tasks, page = [], 0
    while page < 12:
        url = (f"https://api.clickup.com/api/v2/team/{team_id}/task"
               f"?assignees[]={me}&include_closed=false&subtasks=true&page={page}")
        data = clickup_get(url)
        if not data:
            break
        batch = data.get("tasks", [])
        tasks += batch
        if data.get("last_page") or not batch:
            break
        page += 1
    return tasks


def _clickup_task(t, team, done=False):
    """Task grezza dell'API → forma-task del cruscotto (card, o sottotask dentro `children`)."""
    import datetime
    due = None
    if t.get("due_date"):
        due = datetime.datetime.fromtimestamp(int(t["due_date"]) / 1000).strftime("%Y-%m-%d")
    p = t.get("priority") or {}
    prio = PRIO_MAP.get((p.get("priority") or "").lower() if isinstance(p, dict) else "")
    tags = [tg.get("name") for tg in (t.get("tags") or []) if tg.get("name")]
    if not tags:
        tags = [WS_TAG.get(team) or "clickup"]               # il primo tag decide progetto e colore in board
    return {
        "text": t.get("name", ""), "due": due, "prio": prio, "tags": tags,
        "source": "clickup", "cu_id": t.get("id"), "ws": team,
        "url": t.get("url"), "file": None, "line": None,
        "done": done, "children": [],
    }


def _clickup_closed_subtasks(team, parent_id):
    """Sottotask GIÀ CHIUSE (dell'utente) di una madre. La lista principale porta solo le aperte:
    senza queste la barra n/tot tornerebbe indietro a ogni spunta (1/4 → 0/3)."""
    data = clickup_get(f"https://api.clickup.com/api/v2/team/{team}/task"
                       f"?assignees[]={member_id()}&parent={parent_id}&subtasks=true&include_closed=true")
    return [t for t in (data or {}).get("tasks", [])
            if ((t.get("status") or {}).get("type") or "").lower() in DONE_TYPES]


def clickup_live_tasks():
    now = time.time()
    if _LIVE_CACHE["data"] is not None and now - _LIVE_CACHE["t"] < 20:
        return _LIVE_CACHE["data"]
    rows, by_id, born = [], {}, {}
    for team, list_filter in WORKSPACES:
        for t in _clickup_team_tasks(team):
            status = ((t.get("status") or {}).get("status") or "").lower()
            if status in EXCLUDE_STATUS:
                continue
            if list_filter and str((t.get("list") or {}).get("id")) not in list_filter:
                continue
            task = _clickup_task(t, team)
            rows.append((task, t.get("parent")))
            by_id[task["cu_id"]] = task
            born[task["cu_id"]] = int(t.get("date_created") or 0)
    # L'API restituisce le sottotask in lista piatta col campo `parent`: vanno rimesse sotto la madre
    # (se è in lista anche lei). Senza, ogni sottotask diventa una card a sé accanto alla madre.
    up = {task["cu_id"]: parent for task, parent in rows}
    out = []
    for task, parent in rows:
        top = None
        for _ in range(8):                                   # risale fino alla madre di primo livello
            if parent not in by_id:
                break
            top, parent = by_id[parent], up.get(parent)
        if top is None:
            out.append(task)                                 # task normale, o sottotask con la madre fuori lista
        else:
            top["children"].append(task)
    for task in out:
        if not task["children"]:
            continue
        seen = [c["cu_id"] for c in task["children"]]
        for t in _clickup_closed_subtasks(task["ws"], task["cu_id"]):
            if t.get("id") not in seen:
                task["children"].append(_clickup_task(t, task["ws"], done=True))
                born[t.get("id")] = int(t.get("date_created") or 0)
        task["children"].sort(key=lambda c: born.get(c["cu_id"], 0))   # ordine di creazione, come su ClickUp
    _LIVE_CACHE["t"], _LIVE_CACHE["data"] = now, out
    return out


def _reminder_task(r):
    """Promemoria (dal pull live) nella forma-task del cruscotto: entra nella griglia con
    drag&drop e priorità cliccabile, freschi e in ordine Apple (non dal mirror stantio)."""
    return {
        "text": r["name"], "due": r.get("due"), "prio": r.get("prio"),
        "tags": ["promemoria"], "source": "reminder",
        "cu_id": None, "ws": None, "url": None, "file": None, "line": None,
    }


def all_tasks():
    seen, out = set(), []
    # ClickUp non configurato (nessun workspace in brain.json) o senza chiave: nessuna chiamata.
    live = clickup_live_tasks() if (WORKSPACES and load_env().get("CLICKUP_TOKEN")) else None
    if live:
        for t in live:
            key = (t["text"], t["due"], "clickup")
            if key not in seen:
                seen.add(key)
                out.append(t)
    for r in reminders_pull():                               # promemoria freschi (ordine Apple), non dal mirror
        key = (r["name"], r.get("due"), "reminder")
        if key not in seen:
            seen.add(key)
            out.append(_reminder_task(r))
    for root in task_roots():
        if not root.exists():
            continue
        if "reminders-mirror" in str(root):
            continue  # i promemoria arrivano già dal pull live: salta il mirror stantio
        if live is not None and "clickup-mirror" in str(root):
            continue  # ClickUp arriva già live: salta il mirror
        for md in sorted(root.glob("*.md")):
            for t in parse_file(md):
                key = (t["text"], t["due"], t["source"])
                if key not in seen:
                    seen.add(key)
                    out.append(t)
    notes = _load_notes()                                    # note locali per le task non native
    for t in out:
        if not _is_native(t):
            t["note"] = notes.get(_note_key(t), "")
        t.setdefault("note", "")
    return out


# --- Write-back: completa una task sulla sua fonte ---
SECRETS = ROOT / "_local-only" / "secrets" / ".env"
COMPLETE_APPLESCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "reminders" / "complete.applescript"


def load_env():
    env = {}
    try:
        for line in SECRETS.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    except Exception:
        pass
    return env


def clickup_complete(task_id):
    token = load_env().get("CLICKUP_TOKEN")
    if not token:
        return False, "manca CLICKUP_TOKEN in _local-only/secrets/.env"
    req = urllib.request.Request(
        f"https://api.clickup.com/api/v2/task/{task_id}",
        data=json.dumps({"status": "done"}).encode("utf-8"),
        headers={"Authorization": token, "Content-Type": "application/json"},
        method="PUT",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            r.read()
        return True, "ok"
    except Exception as e:
        return False, f"ClickUp API: {e}"


def reminder_complete(name):
    try:
        out = subprocess.run(["osascript", str(COMPLETE_APPLESCRIPT), REM_LIST, name],
                             capture_output=True, text=True, timeout=60)
        res = (out.stdout or out.stderr).strip()
        return res.startswith("OK"), _rem_msg(res)
    except Exception as e:
        return False, f"osascript: {e}"


def native_complete(rel_file, line_no, _text):
    if not rel_file:
        return True, "live (nessun mirror)"
    try:
        f = ROOT / rel_file
        lines = f.read_text(encoding="utf-8").splitlines()
        if isinstance(line_no, int) and 0 <= line_no < len(lines) and "- [ ]" in lines[line_no]:
            lines[line_no] = lines[line_no].replace("- [ ]", "- [x]", 1)
            f.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return True, "ok"
        return False, "riga non trovata o già completata"
    except Exception as e:
        return False, str(e)


# --- Riprogramma (trascini la card su un giorno → cambia la data) ---
RESCHEDULE_APPLESCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "reminders" / "reschedule.applescript"


def _date_to_ms(date_str):
    import datetime
    y, m, d = (int(x) for x in date_str.split("-"))
    return int(datetime.datetime(y, m, d, 12, 0, 0).timestamp() * 1000)


def clickup_set_due(task_id, date_str):
    token = load_env().get("CLICKUP_TOKEN")
    if not token:
        return False, "manca CLICKUP_TOKEN"
    body = {"due_date": _date_to_ms(date_str), "due_date_time": False} if date_str else {"due_date": None}
    req = urllib.request.Request(
        f"https://api.clickup.com/api/v2/task/{task_id}",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": token, "Content-Type": "application/json"},
        method="PUT",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            r.read()
        return True, "ok"
    except Exception as e:
        return False, f"ClickUp API: {e}"


def reminder_reschedule(name, date_str):
    y, m, d = date_str.split("-")
    try:
        out = subprocess.run(["osascript", str(RESCHEDULE_APPLESCRIPT), REM_LIST, name, y, m, d],
                             capture_output=True, text=True, timeout=60)
        res = (out.stdout or out.stderr).strip()
        return res.startswith("OK"), _rem_msg(res)
    except Exception as e:
        return False, f"osascript: {e}"


CLEAR_APPLESCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "reminders" / "clear-due.applescript"


def reminder_clear(name):
    # macOS non permette di togliere la scadenza a un promemoria via AppleScript.
    # Messaggio onesto invece di un errore tecnico (o di un'attesa inutile).
    return False, ("I promemoria Apple non permettono di togliere la scadenza da qui. "
                   "Spostalo in un giorno, oppure toglila dall'app Promemoria.")


def native_set_due(rel_file, line_no, date_str):
    if not rel_file:
        return True, "live (nessun mirror)"
    try:
        f = ROOT / rel_file
        lines = f.read_text(encoding="utf-8").splitlines()
        if not (isinstance(line_no, int) and 0 <= line_no < len(lines)):
            return False, "riga non trovata"
        ln = lines[line_no]
        if not date_str:
            ln = re.sub(r"\s*📅\s*\d{4}-\d{2}-\d{2}", "", ln)
        elif "📅" in ln:
            ln = re.sub(r"📅\s*\d{4}-\d{2}-\d{2}", "📅 " + date_str, ln)
        elif "<!--" in ln:
            ln = ln.replace("<!--", "📅 " + date_str + " <!--", 1)
        else:
            ln = ln.rstrip() + " 📅 " + date_str
        lines[line_no] = ln
        f.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return True, "ok"
    except Exception as e:
        return False, str(e)


# --- Crea task: nuova task nel vault, su Promemoria o su ClickUp, direttamente dal Cruscotto ---
CREATE_APPLESCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "reminders" / "create.applescript"

# Le destinazioni ammesse (allowlist) sono CREATE_TARGETS, costruite da apply_config():
#   - un file `<path>/tasks/aperti.md` per ogni progetto di brain.json (le uniche destinazioni
#     che supportano le sottotask, annidate per indentazione);
#   - la lista di Promemoria, se il modulo è acceso;
#   - le liste ClickUp dichiarate in `clickup.quick_add`.
# Il frontend riceve lo stesso elenco da /api/tasks e ci costruisce il menu: una sola fonte.


def _mirror_name(list_name):
    """File mirror di una lista: nome in minuscolo, il resto diventa trattino ("Lavoro" → lavoro.md)."""
    return (re.sub(r"[^\w]+", "-", list_name.lower()).strip("-") or "promemoria") + ".md"


def _append_reminder_mirror(name, date_str):
    """Aggiunge subito la riga al mirror della lista (se la cartella esiste), così la task compare
    nel Cruscotto senza aspettare il prossimo /task-sync (il pull poi riscrive il file e riconcilia)."""
    mirror = ROOT / "03-task" / "reminders-mirror" / _mirror_name(REM_LIST)
    due = f" 📅 {date_str}" if date_str else ""
    line = f"- [ ] {name} #promemoria{due} <!-- rem-list:{REM_LIST} -->\n"
    try:
        with mirror.open("a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


def reminder_create(name, date_str):
    args = ["osascript", str(CREATE_APPLESCRIPT), REM_LIST, name]
    if date_str:
        args += date_str.split("-")                     # AAAA MM GG
    try:
        out = subprocess.run(args, capture_output=True, text=True, timeout=60)
        res = (out.stdout or out.stderr).strip()
        ok = res.startswith("OK")
        if ok:
            _append_reminder_mirror(name, date_str)
        return ok, _rem_msg(res)
    except Exception as e:
        return False, f"osascript: {e}"


def clickup_create(list_id, name, date_str):
    token = load_env().get("CLICKUP_TOKEN")
    if not token:
        return False, "manca CLICKUP_TOKEN"
    body = {"name": name}
    me = member_id()
    if me.isdigit():
        body["assignees"] = [int(me)]                        # assegnata all'utente: così rientra in board
    if date_str:
        body["due_date"] = _date_to_ms(date_str)
        body["due_date_time"] = False
    req = urllib.request.Request(
        f"https://api.clickup.com/api/v2/list/{list_id}/task",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": token, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            r.read()
        return True, "ok"
    except Exception as e:
        return False, f"ClickUp API: {e}"


def _clean_tag(t):
    """`#pb`, ' Pb ' → 'pb'. Tiene solo word-char/-/ / (come TAG_RE); scarta il resto."""
    t = re.sub(r"[^\w/-]", "", str(t).strip().lstrip("#"))
    return t.lower()


def native_create(rel_path, text, date_str, subtasks, tags=None):
    """Scrive una task madre + sottotask indentate nel file `tasks/*.md` del progetto.
    La sottotask è una riga `- [ ]` rientrata di 4 spazi: il parser (parse_file) la annida
    per indentazione, quindi compare come figlia nel cruscotto senza altre modifiche.
    Il PRIMO tag determina il progetto/colore nel cruscotto (vedi projOf)."""
    root = ROOT.resolve()
    path = (root / rel_path).resolve()
    # allowlist: solo file .md dentro una cartella tasks/ del vault (no path traversal)
    if root not in path.parents or path.suffix != ".md" or path.parent.name != "tasks":
        return False, "percorso non ammesso"
    due = f" 📅 {date_str}" if date_str else ""
    clean_tags = [c for c in (_clean_tag(t) for t in (tags or [])) if c]
    tagstr = "".join(f" #{t}" for t in dict.fromkeys(clean_tags))   # dedup, ordine preservato
    lines = [f"- [ ] {text}{due}{tagstr}"]
    for s in (subtasks or []):
        s = s.strip()
        if s:
            lines.append(f"    - [ ] {s}")                   # 4 spazi = sottotask
    block = "\n".join(lines) + "\n"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        prefix = "" if (existing == "" or existing.endswith("\n")) else "\n"
        with path.open("a", encoding="utf-8") as f:
            f.write(prefix + block)
        return True, "ok"
    except Exception as e:
        return False, f"scrittura: {e}"


# --- Note + sottotask manuali dal dettaglio (modale) ---
# Regola di persistenza: task NATIVE del vault → si scrive nel markdown (file-over-app: la nota
# resta visibile in Obsidian, va in git e nel backup). Task ClickUp/Promemoria → sidecar LOCALE,
# stesso principio della priorità promemoria: il cruscotto non scrive mai sul sistema esterno
# senza il gate di approvazione (CLAUDE §6).
NOTE_FILE = ROOT / "_local-only" / "cruscotto-note.json"
_MD_LOCK = threading.Lock()                                  # le scritture sul markdown sono serializzate


def _is_native(t):
    return (t.get("source") == "native") and bool(t.get("file"))


def _note_key(t):
    return "|".join([str(t.get("cu_id") or ""), str(t.get("source") or ""), str(t.get("text") or "")])


def _load_notes():
    try:
        d = json.loads(NOTE_FILE.read_text(encoding="utf-8"))
        return {str(k): str(v) for k, v in d.items()}
    except Exception:
        return {}


def _save_notes(d):
    try:
        NOTE_FILE.parent.mkdir(parents=True, exist_ok=True)
        NOTE_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        return True
    except Exception:
        return False


def _open_task_file(rel_file):
    """Allowlist identica a native_create: solo .md dentro una cartella tasks/ del vault."""
    root = ROOT.resolve()
    f = (root / (rel_file or "")).resolve()
    if root not in f.parents or f.suffix != ".md" or f.parent.name != "tasks" or not f.is_file():
        return None, None
    try:
        return f, f.read_text(encoding="utf-8").splitlines()
    except Exception:
        return None, None


def _line_still_is(lines, line_no, expect_text):
    """Difesa dal numero di riga stantio: la riga deve essere ancora QUELLA task.
    Senza questo controllo un refresh del file farebbe scrivere sulla task sbagliata."""
    if not isinstance(line_no, int) or not (0 <= line_no < len(lines)):
        return False
    m = TASK_RE.match(lines[line_no])
    if not m:
        return False
    return (not expect_text) or clean(m.group(2)) == expect_text


def _block_end(lines, line_no, indent):
    """Ultima riga appartenente al blocco della task (note + sottotask), saltando le righe vuote."""
    last, j = line_no, line_no + 1
    while j < len(lines):
        ln = lines[j]
        if not ln.strip():
            j += 1
            continue                                         # vuota: il blocco potrebbe continuare sotto
        if len(ln) - len(ln.lstrip()) <= indent:
            break                                            # rientro pari o minore → fine del blocco
        last = j
        j += 1
    return last


def native_set_note(rel_file, line_no, expect_text, note):
    """Riscrive il blocco `> …` subito sotto la riga della task. Nota vuota = blocco rimosso."""
    with _MD_LOCK:
        f, lines = _open_task_file(rel_file)
        if f is None:
            return False, "percorso non ammesso"
        if not _line_still_is(lines, line_no, expect_text):
            return False, "la riga è cambiata sul file: ricarica il cruscotto e riprova"
        indent = len(lines[line_no]) - len(lines[line_no].lstrip())
        j = line_no + 1
        while j < len(lines) and NOTE_RE.match(lines[j]):    # via le note già presenti
            j += 1
        pad = " " * (indent + 4)
        body = (note or "").replace("\r\n", "\n").replace("\r", "\n").strip("\n")
        new = [f"{pad}> {ln}".rstrip() for ln in body.split("\n")] if body.strip() else []
        lines[line_no + 1:j] = new
        try:
            f.write_text("\n".join(lines) + "\n", encoding="utf-8")
        except Exception as e:
            return False, f"scrittura: {e}"
        return True, "ok"


def native_add_subtask(rel_file, line_no, expect_text, text):
    """Aggiunge `    - [ ] testo` in fondo al blocco della task (dopo note e sottotask esistenti)."""
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return False, "testo della sottotask mancante"
    with _MD_LOCK:
        f, lines = _open_task_file(rel_file)
        if f is None:
            return False, "percorso non ammesso"
        if not _line_still_is(lines, line_no, expect_text):
            return False, "la riga è cambiata sul file: ricarica il cruscotto e riprova"
        indent = len(lines[line_no]) - len(lines[line_no].lstrip())
        lines.insert(_block_end(lines, line_no, indent) + 1, f"{' ' * (indent + 4)}- [ ] {text}")
        try:
            f.write_text("\n".join(lines) + "\n", encoding="utf-8")
        except Exception as e:
            return False, f"scrittura: {e}"
        return True, "ok"


def set_note(t, note):
    if _is_native(t):
        return native_set_note(t.get("file"), t.get("line"), t.get("text"), note)
    with _MD_LOCK:                                           # sidecar locale: non tocca ClickUp/Apple
        d = _load_notes()
        k = _note_key(t)
        if (note or "").strip():
            d[k] = note
        else:
            d.pop(k, None)
        return (True, "ok (nota locale)") if _save_notes(d) else (False, "sidecar non scrivibile")


def create_task(target_key, text, date_str, subtasks=None, tags=None):
    tgt = CREATE_TARGETS.get(target_key)
    if not text or not tgt:
        return False, "testo o destinazione mancante"
    if tgt["kind"] == "reminder":
        return reminder_create(text, date_str)
    if tgt["kind"] == "native":
        return native_create(tgt["file"], text, date_str, subtasks, tags)
    return clickup_create(tgt["list"], text, date_str)


def clickup_get(url):
    token = load_env().get("CLICKUP_TOKEN")
    if not token:
        return None
    req = urllib.request.Request(url, headers={"Authorization": token})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
        _CU_STATE["err"] = None
        return data
    except Exception as e:
        _CU_STATE["err"] = str(e)                            # la board lo dice, invece di restare vuota in silenzio
        return None


# --- Menzioni: commenti dove un ALTRO utente @tagga l'utente, che non ha ancora risposto ---
# Rilevamento strutturato (frammento type:"tag" con user.id == utente), non string-match.
# Dove cercare lo dice `clickup.mention_scopes` in brain.json: un workspace intero, oppure solo
# alcuni suoi spazi. Elenco vuoto = modulo spento (la scansione costa una lettura per ogni task).
# "Risolta" = esiste un commento/reply dell'utente con data successiva → non entra.
# Finestra 30gg. Scansione in background (ogni 15 min) → cache; l'endpoint la serve istantanea.
MENTION_WINDOW_DAYS = 30
_MENTIONS = {"items": [], "count": 0, "ts": 0.0}


def _team_tasks_raw(team_id, extra=""):
    tasks, page = [], 0
    while page < 20:
        url = (f"https://api.clickup.com/api/v2/team/{team_id}/task"
               f"?include_closed=false&subtasks=true&page={page}{extra}")
        data = clickup_get(url)
        if not data:
            break
        batch = data.get("tasks", [])
        tasks += batch
        if data.get("last_page") or not batch:
            break
        page += 1
    return tasks


def _norm_comment(c):
    tagged = {(f.get("user") or {}).get("id")
              for f in c.get("comment", []) if f.get("type") == "tag"}
    return {
        "id": str(c.get("id")),
        "author": str((c.get("user") or {}).get("id")),
        "who": (c.get("user") or {}).get("username") or "?",
        "date": int(c.get("date") or 0),
        "tagged": tagged,
        "text": (c.get("comment_text") or "").strip().replace("\n", " "),
    }


def _task_comments(task_id):
    """Commenti + reply di una task, normalizzati (una sola discesa nei thread)."""
    data = clickup_get(f"https://api.clickup.com/api/v2/task/{task_id}/comment")
    if not data:
        return []
    items = []
    for c in data.get("comments", []):
        items.append(_norm_comment(c))
        if int(c.get("reply_count") or 0) > 0:
            rd = clickup_get(f"https://api.clickup.com/api/v2/comment/{c.get('id')}/reply")
            for r in (rd or {}).get("comments", []):
                items.append(_norm_comment(r))
    return items


MENTIONS_CACHE = ROOT / "_local-only" / "cruscotto-mentions.json"
MENTIONS_DISMISSED = ROOT / "_local-only" / "cruscotto-mentions-dismissed.json"
# menzioni scartate a mano dal cruscotto: {comment_id: date_ms della menzione}.
# Locale al Mac; NON tocca ClickUp (scarti la vista, non chiudi/rispondi la task).
_DISMISSED = {}


def _load_dismissed():
    try:
        d = json.loads(MENTIONS_DISMISSED.read_text(encoding="utf-8"))
        return {str(k): int(v) for k, v in d.items()}
    except Exception:
        return {}


def _save_dismissed():
    try:
        MENTIONS_DISMISSED.parent.mkdir(parents=True, exist_ok=True)
        MENTIONS_DISMISSED.write_text(json.dumps(_DISMISSED), encoding="utf-8")
    except Exception:
        pass


def _mention_from(it, t):
    lst = (t.get("list") or {}).get("name") or ""
    fld = (t.get("folder") or {}).get("name") or ""
    if fld.lower() == "hidden":                              # ClickUp: lista fuori da folder
        fld = ""
    return {
        "id": it["id"], "task_id": t.get("id"), "who": it["who"],
        "task": t.get("name", ""), "url": t.get("url"),
        "text": it["text"][:180], "full": it["text"][:800], "date": str(it["date"]),
        "list": lst, "folder": fld,
    }


def _pending_for_task(t, cutoff, me):
    """Menzioni pendenti di UNA task (lista, eventualmente vuota = niente da rispondere)."""
    items = _task_comments(t.get("id"))
    if not items:
        return []
    my_last = max([it["date"] for it in items if it["author"] == str(me)], default=0)
    out = []
    for it in items:
        if it["author"] == str(me) or me not in it["tagged"]:
            continue
        if it["date"] < cutoff or my_last > it["date"]:      # fuori finestra o già risposta
            continue
        out.append(_mention_from(it, t))
    return out


def _scan_since(since_ms):
    """Ricalcola le menzioni delle sole task aggiornate dopo `since_ms` (via date_updated_gt).
    Ritorna {task_id: [menzioni]}; lista vuota = task che ora non ha più menzioni pendenti."""
    cutoff = int(time.time() * 1000) - MENTION_WINDOW_DAYS * 86400 * 1000
    me = member_id()
    if not me.isdigit():
        return {}                                            # utente sconosciuto: niente da cercare
    me = int(me)
    result = {}
    for team, extra in MENTION_SCOPES:
        for t in _team_tasks_raw(team, f"{extra}&date_updated_gt={since_ms}"):
            tid = t.get("id")
            if tid and tid not in result:
                result[tid] = _pending_for_task(t, cutoff, me)
    return result


def _load_cache():
    try:
        d = json.loads(MENTIONS_CACHE.read_text(encoding="utf-8"))
        return list(d.get("items", [])), int(d.get("last_scan_ms", 0))
    except Exception:
        return [], 0


def _save_cache(items, last_scan_ms):
    try:
        MENTIONS_CACHE.parent.mkdir(parents=True, exist_ok=True)
        MENTIONS_CACHE.write_text(
            json.dumps({"items": items, "last_scan_ms": last_scan_ms}), encoding="utf-8")
    except Exception:
        pass


def _notify(n_new):
    msg = (f"{n_new} nuova menzione da rispondere" if n_new == 1
           else f"{n_new} nuove menzioni da rispondere")
    try:
        subprocess.run(["osascript", "-e",
                        f'display notification "{msg}" with title "Cruscotto: ClickUp" '
                        f'sound name "Ping"'], timeout=10)
    except Exception:
        pass


def _mentions_loop():
    """Cold scan (30gg) una sola volta; poi solo incrementale: le task cambiate dall'ultimo
    giro. Persiste la cache su disco → un riavvio riparte incrementale, non da capo."""
    if not (MENTION_SCOPES and load_env().get("CLICKUP_TOKEN")):
        return                                               # modulo spento: nessuna chiamata
    global _DISMISSED
    _DISMISSED = _load_dismissed()
    items, last_scan = _load_cache()
    if items:
        _MENTIONS["items"], _MENTIONS["count"], _MENTIONS["ts"] = items, len(items), time.time()
    prev_ids = {m["id"] for m in items} if items else None
    while True:
        try:
            now_ms = int(time.time() * 1000)
            window_cutoff = now_ms - MENTION_WINDOW_DAYS * 86400 * 1000
            # cold (mai scansionato) = tutta la finestra; altrimenti da poco prima dell'ultimo giro
            since = window_cutoff if last_scan == 0 else max(last_scan - 3 * 60 * 1000, window_cutoff)
            delta = _scan_since(since)
            merged = {(m["task_id"], m["id"]): m for m in _MENTIONS["items"]}
            for k in [k for k in merged if k[0] in delta]:   # via le vecchie delle task riviste
                del merged[k]
            for tid, pend in delta.items():
                for m in pend:
                    merged[(tid, m["id"])] = m
            out = [m for m in merged.values() if int(m["date"]) >= window_cutoff]  # scarta >30gg
            out.sort(key=lambda x: int(x["date"]), reverse=True)
            _MENTIONS["items"], _MENTIONS["count"], _MENTIONS["ts"] = out, len(out), time.time()
            last_scan = now_ms
            _save_cache(out, last_scan)
            pruned = {c: d for c, d in _DISMISSED.items() if d >= window_cutoff}  # scarti fuori finestra
            if len(pruned) != len(_DISMISSED):
                _DISMISSED.clear(); _DISMISSED.update(pruned); _save_dismissed()
            ids = {m["id"] for m in out if str(m["id"]) not in _DISMISSED}  # non ri-notificare le scartate
            if prev_ids is not None and (ids - prev_ids):
                _notify(len(ids - prev_ids))
            prev_ids = ids
        except Exception:
            pass
        time.sleep(15 * 60)


def mentions():
    """Serve la cache calcolata dal loop in background (istantaneo), meno le scartate a mano."""
    return [m for m in _MENTIONS["items"] if str(m.get("id")) not in _DISMISSED]


# --- Delegate: task create DALL'UTENTE e assegnate ad altri (supervisione, sola lettura) ---
# Le liste da guardare sono `clickup.delegated_lists` in brain.json. Elenco vuoto = modulo spento.
_DELEGATED_CACHE = {"t": 0.0, "data": None}


def delegated_tasks():
    now = time.time()
    if _DELEGATED_CACHE["data"] is not None and now - _DELEGATED_CACHE["t"] < 20:
        return _DELEGATED_CACHE["data"]
    me = member_id() if DELEGATED_LISTS else ""
    if not me:
        return []                                            # modulo spento o utente sconosciuto: nessuna lettura
    import datetime
    out = []
    for lst in DELEGATED_LISTS:
        data = clickup_get(f"https://api.clickup.com/api/v2/list/{lst}/task"
                           f"?include_closed=false&subtasks=true")
        if not data:
            continue
        for t in data.get("tasks", []):
            if str((t.get("creator") or {}).get("id")) != me:
                continue                                     # non l'ha creata l'utente
            others = [a for a in (t.get("assignees") or []) if str(a.get("id")) != me]
            if not others:
                continue                                     # non delegata (nessun altro assegnatario)
            due = None
            if t.get("due_date"):
                due = datetime.datetime.fromtimestamp(int(t["due_date"]) / 1000).strftime("%Y-%m-%d")
            st = t.get("status") or {}
            out.append({
                "text": t.get("name", ""), "url": t.get("url"),
                "status": st.get("status") or "", "status_color": st.get("color") or "#8a8d9a",
                "who": ", ".join(a.get("username", "?") for a in others), "due": due,
            })
    out.sort(key=lambda x: (x["due"] is None, x["due"] or ""))  # datati prima, per scadenza
    _DELEGATED_CACHE["t"], _DELEGATED_CACHE["data"] = now, out
    return out


# --- Promemoria Apple: pull LIVE (ordine dell'app) + priorità locale del cruscotto ---
PULL_APPLESCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "reminders" / "pull.applescript"
REMINDER_PRIO_FILE = ROOT / "_local-only" / "cruscotto-reminder-prio.json"
REMINDER_PRIO_W = {"low": 1, "medium": 2, "high": 3}      # priorità locali (Apple non le tocca)
REM_STORES = Path.home() / "Library" / "Group Containers" / "group.com.apple.reminders" / "Container_v1" / "Stores"
REM_STORE_COPY = ROOT / "_local-only" / "reminders-copy.sqlite"    # copia facoltativa dell'archivio, mai su git
_REM_CACHE = {"t": 0.0, "data": None, "err": None, "mode": None}   # err = ultimo pull fallito · mode = live | store


def _reminders_from_store():
    """Ripiego quando Promemoria non espone la lista (succede quando l'account iCloud risulta
    "inattivo" su questo Mac): legge in SOLA LETTURA (`mode=ro`) l'archivio sqlite dell'app, dove
    i promemoria ci sono ancora. Solo la lista REM_LIST: le altre liste non entrano mai nel
    cruscotto. Parte solo con `cruscotto.reminders_store_fallback: true` in brain.json, perché
    leggere i dati di un'altra app fa comparire una richiesta di permesso di macOS."""
    import sqlite3
    best = []
    try:
        files = sorted(p for p in REM_STORES.iterdir() if p.name.startswith("Data-") and p.suffix == ".sqlite")
    except Exception as e:                                   # glob tace, iterdir no: TCC (Accesso completo al disco)
        _REM_CACHE["store_err"] = f"archivio non accessibile al processo: {e}"
        files = []
    if REM_STORE_COPY.exists():                              # copia dell'archivio fatta da una shell che ha accesso
        files.append(REM_STORE_COPY)
    if not files:
        _REM_CACHE["store_err"] = "archivio vuoto o non visibile al processo (privacy macOS?)"
    for f in files:
        try:
            c = sqlite3.connect(f"file:{f}?mode=ro", uri=True)
            rows = c.execute(
                "SELECT r.ZTITLE, r.ZDUEDATE FROM ZREMCDREMINDER r "
                "JOIN ZREMCDBASELIST l ON l.Z_PK = r.ZLIST "
                "WHERE l.ZNAME = ? AND l.ZMARKEDFORDELETION = 0 AND r.ZMARKEDFORDELETION = 0 "
                "AND r.ZCOMPLETED = 0 ORDER BY r.ZICSDISPLAYORDER, r.ZCREATIONDATE", (REM_LIST,)).fetchall()
            c.close()
        except Exception as e:                               # tipico: TCC nega l'archivio al processo launchd
            _REM_CACHE["store_err"] = f"{f.name[:13]}: {e}"
            continue
        if len(rows) > len(best):
            best = rows                                      # più archivi: vince quello che ha la lista viva
    out = []
    for title, due in best:
        title = (title or "").strip()
        if title:
            ds = time.strftime("%Y-%m-%d", time.localtime(due + 978307200)) if due else None  # epoch Apple = 2001
            out.append({"name": title, "due": ds})
    return out


def _rem_msg(raw):
    """Errore osascript → frase leggibile. -1728 sulla lista = Promemoria non trova la lista
    (mai creata, rinominata, cancellata, oppure account iCloud inattivo su questo Mac): non è un
    problema del cruscotto, e il messaggio dice all'utente cosa fare."""
    raw = re.sub(r"^.*?execution error:\s*", "", (raw or "").strip())
    if "-1728" in raw or f'list "{REM_LIST}"' in raw:
        return (f'Promemoria non trova la lista "{REM_LIST}" su questo Mac. Creala nell\'app Promemoria '
                f'con questo nome esatto, oppure cambia "reminders_list" in .claude/config/brain.json. '
                f"Se la lista esiste sull'iPhone ma non qui, va sistemato l'account iCloud di questo Mac. "
                f"Dettaglio: {raw}")
    return raw


def _load_rem_prio():
    try:
        d = json.loads(REMINDER_PRIO_FILE.read_text(encoding="utf-8"))
        return {str(k): str(v) for k, v in d.items() if str(v) in REMINDER_PRIO_W}
    except Exception:
        return {}


def _save_rem_prio(d):
    try:
        REMINDER_PRIO_FILE.parent.mkdir(parents=True, exist_ok=True)
        REMINDER_PRIO_FILE.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def _reminders_from_mirror():
    """Ripiego finché il primo pull non è pronto: legge il mirror su disco (può essere vecchio).
    Legge ogni file della cartella, così non dipende dal nome che gli ha dato chi l'ha scritto."""
    folder = ROOT / "03-task" / "reminders-mirror"
    out = []
    for md in (sorted(folder.glob("*.md")) if folder.is_dir() else []):
        out += [{"name": t["text"], "due": t["due"]} for t in parse_file(md) if t["source"] == "reminder"]
    return out


def _reminders_pull_live():
    """Chiamata BLOCCANTE a osascript (a freddo Reminders è lento per il sync iCloud).
    USATA SOLO dal loop in background, MAI sul percorso di una richiesta HTTP."""
    try:
        out = subprocess.run(["osascript", str(PULL_APPLESCRIPT), REM_LIST],
                             capture_output=True, text=True, timeout=40)
        if out.returncode != 0:
            return None, _rem_msg(out.stderr or out.stdout)
        base = []
        for line in out.stdout.splitlines():
            if not line.strip():
                continue
            parts = line.split("\t")
            name = parts[0].strip()
            due = (parts[1].strip() if len(parts) > 1 else "") or None
            if name:
                base.append({"name": name, "due": due})
        return base, None
    except Exception as e:
        return None, f"osascript: {e}"


def _reminders_tick():
    """Un giro del pull. Se fallisce si tiene l'ultima cache buona MA si registra l'errore: una
    cache che non dice di essere vecchia serve per giorni una fotografia ferma come dato vivo."""
    base, err = _reminders_pull_live()
    if base is not None:
        _REM_CACHE.update(t=time.time(), data=base, err=None, mode="live")
        return
    _REM_CACHE["err"] = err or "pull promemoria fallito"     # prima del ripiego: se quello salta, l'errore resta
    if not REM_STORE_FALLBACK:
        return                                               # ripiego sull'archivio non chiesto in brain.json
    store = _reminders_from_store()
    if store:
        _REM_CACHE.update(data=store, mode="store")          # visibili (dall'archivio), non spuntabili


def _reminders_loop():
    """Aggiorna la cache promemoria in background (osascript lento fuori dal path di richiesta).
    Primo giro subito, poi ogni 30s → /api/tasks resta sempre istantaneo.
    Un giro che salta non deve fermare il thread: un'eccezione non presa lo ucciderebbe, e i
    promemoria resterebbero fermi per giorni senza nessun avviso."""
    while True:
        try:
            _reminders_tick()
        except Exception as e:
            _REM_CACHE["err"] = f"giro promemoria fallito: {e}"
        time.sleep(30)


REM_STALE_S = 300                                            # oltre: il giro è fermo anche se non ha detto perché


def reminders_status():
    """Stato del pull per il banner del frontend: ok, errore leggibile, ora dell'ultimo pull riuscito,
    mode=store quando i promemoria arrivano dall'archivio locale e non dall'app.
    Modulo spento (enabled=False) = nessun banner: non è un guasto."""
    if not REM_ON:
        return {"ok": True, "enabled": False, "list": REM_LIST, "err": None, "mode": None,
                "store_err": None, "since": None}
    t = _REM_CACHE["t"]
    err = _REM_CACHE["err"]
    if err is None and t and time.time() - t > REM_STALE_S:  # giro fermo senza errore: guasto muto
        err = "il giro dei promemoria si è fermato: il cruscotto va riavviato"
    return {"ok": err is None, "enabled": True, "list": REM_LIST, "err": err, "mode": _REM_CACHE["mode"],
            "store_err": _REM_CACHE.get("store_err"),
            "since": time.strftime("%d/%m %H:%M", time.localtime(t)) if t else None}


def reminders_pull():
    """NON bloccante: serve la cache popolata dal loop di background (istantaneo). Finché il primo
    giro non è pronto, ripiega sul mirror su disco. La priorità è un overlay LOCALE applicato fresco.
    Modulo spento = elenco vuoto, senza toccare né l'app né il mirror."""
    if not REM_ON:
        return []
    base = _REM_CACHE["data"]
    if base is None:
        base = _reminders_from_mirror()
    prio = _load_rem_prio()
    return [{**r, "prio": prio.get(r["name"])} for r in base]


# --- Calendario Apple: call/eventi imminenti (SOLA LETTURA, pull LIVE in background) ---
# Facoltativo: parte solo con `cruscotto.calendar: true` in brain.json e se lo script esiste.
CAL_PULL_APPLESCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "calendar" / "pull.applescript"
CAL_WINDOW_DAYS = 7                                          # oggi..+7gg
_CAL_CACHE = {"t": 0.0, "data": None}


def _dur_label(t1, t2):
    """Durata 'inizio→fine' in etichetta compatta (30m · 1h · 1h30). None se all-day/incoerente."""
    try:
        mins = (int(t2[:2]) * 60 + int(t2[3:5])) - (int(t1[:2]) * 60 + int(t1[3:5]))
        if mins <= 0 or mins >= 1440:
            return None
        h, m = divmod(mins, 60)
        return (f"{h}h{m:02d}" if h and m else f"{h}h" if h else f"{m}m")
    except Exception:
        return None


def _calendar_pull_live():
    """BLOCCANTE: osascript su Calendar.app (a freddo è lento). USATA SOLO dal loop di background."""
    try:
        out = subprocess.run(["osascript", str(CAL_PULL_APPLESCRIPT), str(CAL_WINDOW_DAYS)] + CAL_NAMES,
                             capture_output=True, text=True, timeout=45)
        if out.returncode != 0:
            return None
        evs = []
        for line in out.stdout.splitlines():
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            title = parts[0].strip()
            date = (parts[1].strip() or None)
            t1 = (parts[2].strip() or None)
            t2 = parts[3].strip() if len(parts) > 3 else ""
            cal = parts[4].strip() if len(parts) > 4 else ""
            if title and date:
                evs.append({"title": title, "date": date, "time": t1,
                            "end": t2 or None, "dur": _dur_label(t1, t2), "cal": cal})
        evs.sort(key=lambda e: (e["date"], e["time"] or ""))
        return evs
    except Exception:
        return None


def _calendar_loop():
    """Aggiorna la cache calendario in background. Primo giro subito, poi ogni 5 min →
    /api/calendar resta istantaneo (osascript su Calendar mai sul path di richiesta)."""
    while True:
        evs = _calendar_pull_live()
        if evs is not None:
            _CAL_CACHE["t"], _CAL_CACHE["data"] = time.time(), evs
        time.sleep(300)


def calendar_events():
    """NON bloccante: serve la cache popolata dal loop. Lista vuota finché il primo giro non è pronto."""
    return _CAL_CACHE["data"] or []


# --- Configurazione: da brain.json alle variabili di modulo ---
def _ids(values):
    """Elenco di id come stringhe non vuote (in brain.json possono arrivare numeri o stringhe)."""
    return [str(v).strip() for v in _list(values) if not isinstance(v, (dict, list)) and str(v).strip()]


def _list(value):
    """Un elenco resta un elenco; un valore singolo scritto al posto dell'elenco diventa [valore]."""
    if isinstance(value, list):
        return value
    return [value] if value else []


def apply_config():
    """Legge `.claude/config/brain.json` e riempie le variabili di modulo. Un campo mancante, vuoto
    o scritto male lascia spento quel pezzo: da qui non deve mai uscire un errore.

    Campi letti:
      cruscotto.port                      porta locale (default 8765)
      cruscotto.reminders                 false = Promemoria spento (default acceso, solo macOS)
      cruscotto.reminders_store_fallback  true = se il pull fallisce, leggi l'archivio locale dell'app
      cruscotto.calendar                  true = mostra gli eventi di Calendario (default spento)
      calendars                           nomi dei calendari da leggere (vuoto = tutti)
      reminders_list                      nome della lista di Promemoria da mostrare
      projects                            un filtro e una destinazione `<path>/tasks/aperti.md` a testa
      clickup.member_id                   id utente ClickUp (vuoto = lo si chiede a ClickUp)
      clickup.workspaces                  [{"id": "...", "tag": "...", "lists": ["..."]}]
      clickup.exclude_statuses            stati che non entrano in board
      clickup.quick_add                   {"Etichetta nel menu": "id lista"}
      clickup.delegated_lists             ["id lista", ...]
      clickup.mention_scopes              [{"workspace": "...", "spaces": ["..."]}]
    """
    global PORT, MEMBER_ID, WORKSPACES, WS_TAG, EXCLUDE_STATUS, MENTION_SCOPES, DELEGATED_LISTS
    global CREATE_TARGETS, PROJECTS, REM_LIST, REM_ON, REM_STORE_FALLBACK, CAL_ON, CAL_NAMES
    cfg = brain_config.load(ROOT)
    app = cfg.get("cruscotto") if isinstance(cfg.get("cruscotto"), dict) else {}
    cu = brain_config.clickup(ROOT)
    cu = cu if isinstance(cu, dict) else {}
    try:
        PORT = int(app.get("port") or 8765)
    except (TypeError, ValueError):
        PORT = 8765
    if not 1024 <= PORT <= 65535:                            # fuori dall'intervallo utilizzabile: default
        PORT = 8765

    mac = sys.platform == "darwin"                           # Promemoria e Calendario passano da osascript
    try:
        REM_LIST = brain_config.reminders_list(ROOT)
    except Exception:                                        # valore del tipo sbagliato: resta il default
        REM_LIST = str(brain_config.DEFAULTS.get("reminders_list") or "Lavoro")
    REM_ON = mac and app.get("reminders", True) is not False
    REM_STORE_FALLBACK = app.get("reminders_store_fallback") is True
    CAL_ON = mac and app.get("calendar") is True and CAL_PULL_APPLESCRIPT.is_file()
    try:
        CAL_NAMES = list(brain_config.calendars(ROOT))
    except Exception:                                        # lettore senza `calendars`: tutti i calendari
        CAL_NAMES = []

    MEMBER_ID = str(cu.get("member_id") or "").strip()
    WORKSPACES, WS_TAG = [], {}
    for w in _list(cu.get("workspaces")):
        if not isinstance(w, dict):
            w = {"id": w}                                    # ammesso anche il solo id
        team = str(w.get("id") or "").strip()
        if team:
            WORKSPACES.append((team, frozenset(_ids(w.get("lists"))) or None))
            WS_TAG[team] = _clean_tag(w.get("tag") or "") or "clickup"
    EXCLUDE_STATUS = {s.lower() for s in _ids(cu.get("exclude_statuses"))}
    MENTION_SCOPES = []
    for m in _list(cu.get("mention_scopes")):
        if not isinstance(m, dict):
            m = {"workspace": m}                             # ammesso anche il solo id: tutto il workspace
        team = str(m.get("workspace") or "").strip()
        if team:
            MENTION_SCOPES.append((team, "".join(f"&space_ids[]={s}" for s in _ids(m.get("spaces")))))
    DELEGATED_LISTS = _ids(cu.get("delegated_lists"))

    PROJECTS, targets = [], {}
    try:
        declared = brain_config.projects(ROOT)
    except Exception:                                        # `projects` del tipo sbagliato: nessun progetto
        declared = []
    for p in declared:                                       # prima il vault: funziona sempre
        tag = _clean_tag(p["id"])
        PROJECTS.append({"id": p["id"], "path": p["path"], "tag": tag})
        targets[f"vault-{p['id']}"] = {"kind": "native", "file": f"{p['path']}/tasks/aperti.md",
                                       "label": f"Vault · {p['id']}", "tag": tag}
    if REM_ON:
        targets["reminder"] = {"kind": "reminder", "label": f"Promemoria · {REM_LIST}"}
    quick = cu.get("quick_add") if isinstance(cu.get("quick_add"), dict) else {}
    for label, lst in quick.items():
        lst = "" if isinstance(lst, (dict, list)) else str(lst or "").strip()
        if lst and not str(label).startswith("_"):           # le chiavi con `_` davanti sono note, non liste
            targets[f"clickup-{lst}"] = {"kind": "clickup", "list": lst, "label": f"ClickUp · {label}"}
    CREATE_TARGETS = targets


def clickup_status():
    """Stato di ClickUp per il frontend: una riga discreta a piè di pagina, mai un errore a schermo."""
    has_token = bool(load_env().get("CLICKUP_TOKEN"))
    st = {"on": False, "mentions": bool(MENTION_SCOPES and has_token),
          "delegated": bool(DELEGATED_LISTS and has_token)}
    if not (WORKSPACES or MENTION_SCOPES or DELEGATED_LISTS):
        st["msg"] = "ClickUp non configurato"
    elif not has_token:
        st["msg"] = "ClickUp: manca la chiave CLICKUP_TOKEN"
    elif _CU_STATE["err"]:
        st["msg"] = f"ClickUp non raggiungibile ({_CU_STATE['err']})"
    else:
        st.update(on=True, msg="connesso a ClickUp")
    return st


def board_payload():
    """Risposta di /api/tasks: le task, lo stato delle fonti, e ciò che serve al frontend per
    costruire filtri, colori e menu delle destinazioni senza elenchi cablati nella pagina."""
    return {
        "tasks": all_tasks(),
        "reminders": reminders_status(),
        "clickup": clickup_status(),
        "projects": PROJECTS,
        "targets": [{"key": k, "label": v["label"], "kind": v["kind"], "tag": v.get("tag", "")}
                    for k, v in CREATE_TARGETS.items()],
    }


apply_config()


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.startswith("/api/tasks"):
            self._send(200, json.dumps(board_payload(), ensure_ascii=False))
            return
        if self.path.startswith("/api/mentions"):
            vis = mentions()
            self._send(200, json.dumps(
                {"mentions": vis, "count": len(vis), "ts": _MENTIONS["ts"]},
                ensure_ascii=False))
            return
        if self.path.startswith("/api/delegated"):
            self._send(200, json.dumps({"delegated": delegated_tasks()}, ensure_ascii=False))
            return
        if self.path.startswith("/api/reminders"):
            self._send(200, json.dumps({"reminders": reminders_pull()}, ensure_ascii=False))
            return
        if self.path.startswith("/api/calendar"):
            self._send(200, json.dumps({"calendar": calendar_events()}, ensure_ascii=False))
            return
        rel = "index.html" if self.path in ("/", "") else self.path.split("?")[0].lstrip("/")
        f = (STATIC / rel).resolve()
        if not str(f).startswith(str(STATIC.resolve())) or not f.is_file():
            self._send(404, "not found", "text/plain")
            return
        ctype = {".html": "text/html", ".css": "text/css",
                 ".js": "application/javascript", ".json": "application/manifest+json",
                 ".png": "image/png", ".svg": "image/svg+xml"}.get(f.suffix, "text/plain")
        self._send(200, f.read_bytes(), ctype)

    def do_POST(self):
        if self.path not in ("/api/complete", "/api/reschedule", "/api/create",
                             "/api/mentions/dismiss", "/api/reminder-prio",
                             "/api/note", "/api/subtask"):
            self._send(404, json.dumps({"error": "not found"}))
            return
        length = int(self.headers.get("Content-Length", 0))
        try:
            b = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            self._send(400, json.dumps({"error": "bad json"}))
            return
        if self.path == "/api/reminder-prio":
            name = (b.get("name") or "").strip()
            prio = b.get("prio")
            d = _load_rem_prio()
            if name:
                if prio in REMINDER_PRIO_W:
                    d[name] = prio
                else:
                    d.pop(name, None)                        # prio null/"" → azzera
                _save_rem_prio(d)
            self._send(200, json.dumps({"ok": bool(name)}))
            return
        if self.path == "/api/mentions/dismiss":
            cid = str(b.get("id") or "")
            if cid:
                item = next((m for m in _MENTIONS["items"] if str(m.get("id")) == cid), None)
                _DISMISSED[cid] = int(item["date"]) if item else int(time.time() * 1000)
                _save_dismissed()
            self._send(200, json.dumps({"ok": bool(cid)}))
            return
        if self.path == "/api/note":
            ok, msg = set_note(b, b.get("note") or "")
            self._send(200 if ok else 500, json.dumps({"ok": ok, "msg": msg}, ensure_ascii=False))
            return
        if self.path == "/api/subtask":
            if not _is_native(b):
                # ClickUp: la creazione va dietro al gate di approvazione (CLAUDE §6), non da qui.
                # Promemoria Apple: non ha il concetto di sottotask.
                self._send(400, json.dumps(
                    {"ok": False, "msg": "sottotask aggiungibili solo sulle task native del vault"},
                    ensure_ascii=False))
                return
            ok, msg = native_add_subtask(b.get("file"), b.get("line"), b.get("text"), b.get("subtask"))
            self._send(200 if ok else 500, json.dumps({"ok": ok, "msg": msg}, ensure_ascii=False))
            return
        if self.path == "/api/create":
            text = (b.get("text") or "").strip()
            subs = b.get("subtasks") or []
            tags = b.get("tags") or []
            ok, msg = create_task(b.get("target"), text, b.get("due") or None, subs, tags)
            if ok and b.get("target") == "reminder" and _REM_CACHE["data"] is not None:
                _REM_CACHE["data"] = _REM_CACHE["data"] + [{"name": text, "due": b.get("due") or None}]
            self._send(200 if ok else 500, json.dumps({"ok": ok, "msg": msg}, ensure_ascii=False))
            return
        src = b.get("source")
        if self.path == "/api/complete":
            if src == "clickup":
                ok, msg = clickup_complete(b.get("cu_id"))
                if ok:
                    native_complete(b.get("file"), b.get("line"), None)  # segna [x] nel mirror
            elif src == "reminder":
                ok, msg = reminder_complete(b.get("text"))
                if ok:
                    native_complete(b.get("file"), b.get("line"), None)
                    if _REM_CACHE["data"] is not None:        # via subito dalla cache (Apple già chiuso)
                        _REM_CACHE["data"] = [r for r in _REM_CACHE["data"] if r["name"] != b.get("text")]

            else:
                ok, msg = native_complete(b.get("file"), b.get("line"), b.get("text"))
        else:  # /api/reschedule
            date = b.get("due") or None
            if src == "clickup":
                ok, msg = clickup_set_due(b.get("cu_id"), date)
                if ok:
                    native_set_due(b.get("file"), b.get("line"), date)
            elif src == "reminder":
                ok, msg = reminder_reschedule(b.get("text"), date) if date else reminder_clear(b.get("text"))
                if ok:
                    native_set_due(b.get("file"), b.get("line"), date)
                    if _REM_CACHE["data"] is not None:        # aggiorna la due nella cache (drag&drop)
                        _REM_CACHE["data"] = [{**r, "due": date} if r["name"] == b.get("text") else r
                                              for r in _REM_CACHE["data"]]
            else:
                ok, msg = native_set_due(b.get("file"), b.get("line"), date)
        self._send(200 if ok else 500, json.dumps({"ok": ok, "msg": msg}, ensure_ascii=False))

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    url = f"http://{HOST}:{PORT}"
    if "--url" in sys.argv:                                  # per il lanciatore: la porta ha una sola fonte
        print(url)
        sys.exit(0)
    try:
        httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    except OSError as e:
        sys.exit(f"Cruscotto: la porta {PORT} non è disponibile ({e}). "
                 f"Forse è già acceso: prova ad aprire {url}")
    print(f"Cruscotto web → {url}   (Ctrl+C per fermare)", flush=True)
    print(f"  ClickUp: {clickup_status()['msg']}", flush=True)
    print("  Promemoria: " + (f'lista "{REM_LIST}"' if REM_ON else "spento"), flush=True)
    print("  Calendario: " + ("acceso" if CAL_ON else "spento"), flush=True)
    # Ogni fonte lenta ha il suo giro in background; una fonte spenta non fa partire nulla.
    if MENTION_SCOPES:
        threading.Thread(target=_mentions_loop, daemon=True).start()
    if REM_ON:
        threading.Thread(target=_reminders_loop, daemon=True).start()
        for _ in range(40):                                  # fino a ~8s: dopo un riavvio la board non deve
            if _REM_CACHE["t"] or _REM_CACHE["err"]:         # uscire senza promemoria (primo giro non ancora fatto)
                break
            time.sleep(0.2)
    if CAL_ON:
        threading.Thread(target=_calendar_loop, daemon=True).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
