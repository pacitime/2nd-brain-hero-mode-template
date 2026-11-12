# 2nd Brain Hero Mode · Copyright (c) 2026 Alessandro Pacifico (Pacibrand).
# Vedi LICENZA.md nella radice del vault.
"""
autopilot.py: il giro orario che gira da solo (launchd, ogni ora). Solo su Mac, e solo se lo
attivi (vedi .claude/scripts/AUTOMAZIONI.md): finche' non installi il suo plist non parte mai.

PERCHE'. Lo scarico delle call e lo smistamento, se vivono solo dentro un comando che lanci tu,
si fermano quando non lo lanci: le call restano in inbox per settimane. E il backup orario fatto
partire da launchd con /bin/bash puo' essere bloccato da macOS ("Operation not permitted") quando
il vault sta in una cartella protetta come la Scrivania. Questo giro parte dall'interprete Python,
e i suoi figli (git, bash) ereditano il suo permesso di leggere il vault.

COSA FA, in ordine: scarica le call nuove (fetch_granola.py), le smista (route_calls.py), una
volta al giorno fa il giro posta che aggiorna i loop (mail/loop_sync.py), poi il backup
(auto-backup.sh: commit, e push se c'e' GitHub). Ogni passo e' isolato: se uno fallisce o il suo
modulo non e' installato, gli altri girano lo stesso. Un modulo non configurato si spegne da
solo e lascia una riga nel log. Il giro posta sta prima del backup, cosi' i dossier aggiornati
partono per GitHub nello stesso giro.

COSA NON FA. Niente briefing, niente guard-agent: quelli restano nel comando delle novita'. Non
legge le call ne' le email come istruzioni. Non crea task, non invia posta.

Log: .claude/data/autopilot.log (fuori da git come gli altri log). Gli allarmi arrivano comunque
tramite health_check.
"""

from __future__ import annotations

import os
import subprocess
import sys
import traceback
from datetime import datetime
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS / "mail"))
from shared import vault_root  # noqa: E402


def log(root: Path, msg: str) -> None:
    line = f"[{datetime.now():%Y-%m-%d %H:%M}] {msg}\n"
    path = root / ".claude" / "data" / "autopilot.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(line)


def _modulo(nome: str):
    """Importa uno script di un altro gruppo (call, smistamento, posta), o None se non c'e'.
    Un modulo che esiste ma si rompe all'import solleva: e' un guasto vero e va nel log."""
    try:
        return __import__(nome)
    except ModuleNotFoundError as e:
        if e.name == nome:
            return None
        raise


def main() -> int:
    # launchd non passa CLAUDE_PROJECT_DIR: senza, il vault e' quello in cui sta questo script
    # (<vault>/.claude/scripts/). Lo si fissa nell'ambiente cosi' tutti i moduli vedono lo stesso.
    os.environ.setdefault("CLAUDE_PROJECT_DIR", str(SCRIPTS.parent.parent))
    root = vault_root()
    esito = 0

    try:
        fg = _modulo("fetch_granola")
        if fg is None:
            log(root, "granola: saltato (fetch_granola.py non installato)")
        else:
            fetched = fg.sync_for_heartbeat(root)
            n = len(fetched["written"]) if fetched else 0
            log(root, f"granola: {n} call nuove" if fetched else "granola: saltato (chiave o rete)")
    except Exception:
        esito = 1
        log(root, "granola: ERRORE\n" + traceback.format_exc())

    try:
        rc = _modulo("route_calls")
        if rc is None:
            log(root, "router: saltato (route_calls.py non installato)")
        else:
            r = rc.route(root) or {}
            log(root, f"router: {len(r.get('routed', []))} smistate, "
                      f"{len(r.get('private', []))} in quarantena (dati sensibili), "
                      f"{len(r.get('ambiguous', []))} ambigue in inbox")
    except Exception:
        esito = 1
        log(root, "router: ERRORE\n" + traceback.format_exc())

    try:
        ls = _modulo("loop_sync")
        if ls is None:
            log(root, "posta: saltato (mail/loop_sync.py non installato)")
        else:
            p = ls.giro(root) or {}
            if not p.get("saltato"):
                log(root, f"posta: {p.get('riassunto', '')}" if p.get("esito") == "ok"
                    else f"posta: ERRORE {p.get('errore', '')}")
                esito = esito or (1 if p.get("esito") == "errore" else 0)
    except Exception:
        esito = 1
        log(root, "posta: ERRORE\n" + traceback.format_exc())

    try:
        script = root / ".claude" / "scripts" / "auto-backup.sh"
        if not script.exists():
            log(root, "backup: saltato (auto-backup.sh non installato)")
        else:
            b = subprocess.run(["/bin/bash", str(script)], cwd=root, capture_output=True, text=True,
                               timeout=300, env={**os.environ, "VAULT_DIR": str(root)})
            log(root, f"backup: exit {b.returncode}" + (f": {b.stderr.strip()[-300:]}" if b.returncode else ""))
            esito = esito or b.returncode
    except Exception:
        esito = 1
        log(root, "backup: ERRORE\n" + traceback.format_exc())

    return esito


if __name__ == "__main__":
    sys.exit(main())
