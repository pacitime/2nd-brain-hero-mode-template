# 2nd Brain Hero Mode · Copyright (c) 2026 Alessandro Pacifico (Pacibrand).
# Vedi LICENZA.md nella radice del vault.
"""
brain_config.py: lettura della configurazione unica del vault (`.claude/config/brain.json`).

Tutto cio' che cambia da una persona all'altra sta in quel file e non nel codice: i progetti e
le parole che li fanno riconoscere, la lista di Promemoria, i workspace ClickUp. Gli script
leggono da qui, cosi' aggiungere un progetto vuol dire toccare una riga di JSON e non sei file.

Regole:
- il file puo' mancare o essere incompleto: ogni funzione ha un default sensato e non solleva;
- qui dentro non ci sono segreti. Le chiavi vivono in `_local-only/secrets/.env`.

Uso:
    from brain_config import load, projects, routing, owner
"""

from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULTS: dict = {
    "owner_name": "",
    "git_author": "",
    "projects": [],
    "extra_routes": [],
    "reminders_list": "Lavoro",
    "calendars": [],
    "mail": {"enabled": False, "accounts": [], "noise": [], "health_extra": [], "no_edit": []},
    # Forma dei campi: vedi `_leggimi` in brain.json e `apply_config` in apps/cruscotto/server.py.
    "clickup": {"member_id": "", "workspaces": [], "exclude_statuses": ["done", "complete", "closed"],
                "quick_add": {}, "delegated_lists": [], "mention_scopes": []},
    "cruscotto": {"port": 8765, "reminders": True, "reminders_store_fallback": False, "calendar": False},
}


def vault_root() -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))


def config_path(root: Path | None = None) -> Path:
    return (root or vault_root()) / ".claude" / "config" / "brain.json"


def load(root: Path | None = None) -> dict:
    """Configurazione con i default riempiti. File assente o rotto: solo i default."""
    cfg = json.loads(json.dumps(DEFAULTS))  # copia profonda
    try:
        raw = json.loads(config_path(root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return cfg
    if not isinstance(raw, dict):
        return cfg
    for key, value in raw.items():
        if isinstance(value, dict) and isinstance(cfg.get(key), dict):
            cfg[key].update(value)
        else:
            cfg[key] = value
    return cfg


def owner(root: Path | None = None) -> str:
    """Nome di chi usa il vault, o 'l'utente' se non e' stato ancora scritto."""
    return (load(root).get("owner_name") or "").strip() or "l'utente"


def projects(root: Path | None = None) -> list[dict]:
    """Progetti dichiarati: [{id, path, keywords, title_only, alias}]. Scarta le voci senza id o path.

    `alias` = i nomi con cui l'utente chiama il progetto in chat (li usa l'hook del contesto di
    progetto). Campo assente o vuoto: vale l'id."""
    out = []
    for p in load(root).get("projects") or []:
        if isinstance(p, dict) and p.get("id") and p.get("path"):
            out.append({
                "id": str(p["id"]),
                "path": str(p["path"]).strip("/"),
                "keywords": [str(k).lower() for k in p.get("keywords") or []],
                "title_only": [str(k).lower() for k in p.get("title_only") or []],
                "alias": _strings(p.get("alias")) or [str(p["id"])],
            })
    return out


def routing(root: Path | None = None) -> list[dict]:
    """Mappa per lo smistamento delle call, nel formato che usa route_calls.py:
    [{"project": id, "dest": (parti, del, percorso), "keywords": [...], "title_only": [...]}].

    I progetti vanno in `<path>/knowledge/calls`; le `extra_routes` dichiarano la loro
    destinazione per intero (es. la cartella call del pilastro fiscale)."""
    out = []
    for p in projects(root):
        out.append({
            "project": p["id"],
            "dest": tuple(p["path"].split("/")) + ("knowledge", "calls"),
            "keywords": p["keywords"],
            "title_only": p["title_only"],
        })
    for r in load(root).get("extra_routes") or []:
        if isinstance(r, dict) and r.get("id") and r.get("dest"):
            out.append({
                "project": str(r["id"]),
                "dest": tuple(str(r["dest"]).strip("/").split("/")),
                "keywords": [str(k).lower() for k in r.get("keywords") or []],
                "title_only": [str(k).lower() for k in r.get("title_only") or []],
            })
    return out


def reminders_list(root: Path | None = None) -> str:
    return (load(root).get("reminders_list") or "").strip() or "Lavoro"


def _strings(value) -> list[str]:
    """Lista di stringhe non vuote. Qualunque altra cosa (assente, numero, testo solo): lista vuota."""
    if not isinstance(value, list):
        return []
    return [str(v).strip() for v in value if isinstance(v, str) and v.strip()]


def calendars(root: Path | None = None) -> list[str]:
    """Nomi dei calendari di Apple Calendar da leggere (`calendar/pull.applescript`).
    Lista vuota = tutti i calendari."""
    return _strings(load(root).get("calendars"))


def mail(root: Path | None = None) -> dict:
    """Configurazione del modulo posta (`.claude/scripts/mail/`), gia' ripulita:
    {enabled, accounts, noise, health_extra, no_edit}.

    Il modulo e' SPENTO finche' `enabled` non e' esattamente `true` E `accounts` non contiene
    almeno un nome di account di Apple Mail: nel dubbio non si legge la posta di nessuno."""
    raw = load(root).get("mail")
    raw = raw if isinstance(raw, dict) else {}
    accounts = _strings(raw.get("accounts"))
    return {
        "enabled": raw.get("enabled") is True and bool(accounts),
        "accounts": accounts,
        "noise": _strings(raw.get("noise")),
        "health_extra": _strings(raw.get("health_extra")),
        "no_edit": [p.strip("/") for p in _strings(raw.get("no_edit")) if p.strip("/")],
    }


def clickup(root: Path | None = None) -> dict:
    return load(root).get("clickup") or dict(DEFAULTS["clickup"])


if __name__ == "__main__":
    cfg = load()
    print(f"proprietario: {owner()}")
    print(f"progetti: {[p['id'] for p in projects()]}")
    print(f"lista promemoria: {reminders_list()}")
    print(f"workspace ClickUp: {len(cfg['clickup'].get('workspaces') or [])}")
