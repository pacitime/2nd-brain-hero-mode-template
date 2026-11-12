# 2nd Brain Hero Mode · Copyright (c) 2026 Alessandro Pacifico (Pacibrand).
# Vedi LICENZA.md nella radice del vault.
"""
Hook PreToolUse: ogni server Slack collegato a Claude e' in sola lettura.

I server MCP di Slack espongono anche strumenti che scrivono (invio e programmazione di
messaggi, canvas, liste, reazioni, upload). Regola del vault: l'agente opera da advisor,
legge e prepara bozze, non invia. Quindi qui passano solo gli strumenti che leggono,
cercano o creano una bozza; tutto il resto e' bloccato.

Vale per qualunque strumento MCP che abbia "slack" nel nome (il matcher in
`.claude/settings.json` e' `mcp__.*[Ss]lack.*`): non importa come hai chiamato il server.
Per lasciare che Claude scriva su Slack si toglie questo hook da `settings.json`
(lo decide l'utente, non l'agente).

Lista di ammessi, non di vietati: i nomi degli strumenti di scrittura non si conoscono
tutti, e uno nuovo aggiunto da Slack deve restare chiuso finche' qualcuno non lo guarda.
Nel dubbio il nome non passa.

Exit codes:
  0 = consenti (il tool prosegue)
  2 = blocca (stderr mostrato a Claude come feedback)
"""

from __future__ import annotations

import json
import re
import sys

SLACK_TOOL = re.compile(r"^mcp__.*slack", re.IGNORECASE)
READ_VERBS = re.compile(r"(search|read|get|list)", re.IGNORECASE)
WRITE_VERBS = re.compile(
    r"(send|schedule|post|create|update|delete|upload|add|remove|invite|set|"
    r"write|edit|archive|join|leave|kick|rename|pin|mark)",
    re.IGNORECASE,
)
# Una bozza resta nel compositore dell'utente: la invia lui a mano.
DRAFT = re.compile(r"draft", re.IGNORECASE)


def is_slack_tool(tool_name: str) -> bool:
    return bool(SLACK_TOOL.search(tool_name or ""))


def is_allowed(tool_name: str) -> bool:
    short = tool_name.rsplit("__", 1)[-1]
    if DRAFT.search(short):
        return True
    return bool(READ_VERBS.search(short)) and not WRITE_VERBS.search(short)


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    tool_name = data.get("tool_name", "")
    if not is_slack_tool(tool_name):
        return 0
    if is_allowed(tool_name):
        return 0
    print(
        f"BLOCCATO: {tool_name} scrive su Slack. Slack qui e' in sola lettura: si legge, "
        "si cerca, si prepara una bozza; l'invio lo fa l'utente a mano.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
