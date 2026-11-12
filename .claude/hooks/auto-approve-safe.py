# 2nd Brain Hero Mode · Copyright (c) 2026 Alessandro Pacifico (Pacibrand).
# Vedi LICENZA.md nella radice del vault.
"""
Hook PreToolUse (Bash): auto-approva i comandi SICURI/REVERSIBILI, così non chiedono conferma.

Filosofia (coerente con i capisaldi del vault): la sicurezza vera la fa
`block-secrets.py` in modo DETERMINISTICO (blocca segreti, cancellazioni distruttive,
scritture fuori dalla working dir). Il prompt di permesso è solo attrito. Qui togliamo
l'attrito per i comandi sicuri, lasciando col GATE solo quelli conseguenti / esterni /
irreversibili.

Logica di `decide(cmd)`:
- se il comando è tra quelli "sempre da confermare" (commit/push, curl ESTERNO, install, sudo, rm…)
  → None (nessuna decisione: resta il prompt normale);
- se `block-secrets` lo bloccherebbe → None (lo bloccherà lui: è il veto);
- altrimenti → "allow" (niente prompt).

`block-secrets` resta attivo come veto indipendente sullo stesso evento: un "allow" qui NON
può far passare un comando che block-secrets blocca (auto-approve si astiene in quel caso).

Output: se "allow", stampa il JSON con permissionDecision=allow; altrimenti exit 0 muto.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

# Comandi che restano SEMPRE col gate umano (conseguenza / esterno / irreversibile).
ALWAYS_ASK: list[str] = [
    r"\bgit\s+(commit|push|reset|rebase|merge|clean|checkout|restore|tag|remote)\b",
    r"\b(wget|nc|ncat|ssh|scp|sftp|rsync|telnet)\b",  # curl gestito a parte (localhost = ok)
    r"\b(npm|pnpm|yarn|npx|pip|pip3|brew|gem|cargo)\s+\w",
    r"\b(sudo|launchctl|systemctl|chmod|chown|shutdown|reboot)\b",  # tolti: osascript/kill/killall/defaults (locali, uso quotidiano)
    r"\brm\b",
    r"\brmdir\b",
]


def _load_block_secrets():
    p = Path(__file__).resolve().parent / "block-secrets.py"
    spec = importlib.util.spec_from_file_location("block_secrets", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def decide(command: str) -> str | None:
    """Ritorna 'allow' se il comando è sicuro da auto-approvare, altrimenti None."""
    cmd = command or ""
    for pat in ALWAYS_ASK:
        if re.search(pat, cmd, re.IGNORECASE):
            return None
    # curl: auto-approva solo verso localhost (es. cruscotto 127.0.0.1); verso URL esterni → gate.
    if re.search(r"\bcurl\b", cmd, re.IGNORECASE) and not re.search(
        r"127\.0\.0\.1|localhost|\[::1\]", cmd, re.IGNORECASE
    ):
        return None
    try:
        bs = _load_block_secrets()
        if bs.check_bash_command(cmd):
            return None  # block-secrets lo bloccherebbe: astieniti (lui è il veto)
    except Exception:
        return None  # nel dubbio, prompt normale
    return "allow"


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)
    if data.get("tool_name") != "Bash":
        sys.exit(0)
    if decide(data.get("tool_input", {}).get("command", "")) == "allow":
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": "comando sicuro/reversibile (auto-approvato; block-secrets resta il veto)",
            }
        }))
    sys.exit(0)


if __name__ == "__main__":
    main()
