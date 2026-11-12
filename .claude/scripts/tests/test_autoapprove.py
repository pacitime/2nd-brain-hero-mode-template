# 2nd Brain Hero Mode · Copyright (c) 2026 Alessandro Pacifico (Pacibrand).
# Vedi LICENZA.md nella radice del vault.
"""
Test dell'hook auto-approve-safe: verifica che i comandi sicuri siano auto-approvati e che
quelli conseguenti/pericolosi restino col gate. Deve dare "N/N test passati".

    python3 .claude/scripts/tests/test_autoapprove.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HOOKS = Path(__file__).resolve().parent.parent.parent / "hooks"
spec = importlib.util.spec_from_file_location("auto_approve_safe", HOOKS / "auto-approve-safe.py")
aa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(aa)

results: list[tuple[bool, str]] = []


def check(cond: bool, label: str) -> None:
    results.append((bool(cond), label))
    print(f"  {'[OK ]' if cond else '[FAIL]'} {label}")


# --- devono essere AUTO-APPROVATI (sicuri / reversibili) ---
ALLOW = [
    "ls -la",
    "cat 02-memoria/me.md",
    "grep -rn fornitore 10-lavoro",
    "find 10-lavoro -type f",
    "python3 .claude/scripts/tests/test_memoria_sessione.py",
    "python3 .claude/skills/llm-wiki/scripts/wiki_ops.py lint --wiki-dir 02-memoria/wiki",
    "mkdir -p 10-lavoro/nuovo/knowledge",
    "cp _TEMPLATE-progetto/README.md 10-lavoro/x/README.md",
    "for d in a b c; do echo $d; done",
    "git status",
    "git diff --stat",
    "wc -l 01-daily/2030-01-10.md",
    "osascript -e 'tell application \"Reminders\" to get name of every list'",  # automazione locale
    "curl -s http://127.0.0.1:8765/api/tasks",   # curl localhost = ok
    "pkill -f cruscotto/server.py",              # kill locale
]

# --- devono restare COL GATE (None) ---
GATE = [
    "git commit -m 'x'",
    "git push origin main",
    "curl -s https://api.example.com/x",   # curl ESTERNO → gate
    "osascript -e 'do shell script \"sudo rm -rf /\"'",   # sudo/rm-rf dentro osascript → gate/veto
    "rm nota.md",
    "rm -rf 10-lavoro",
    "curl https://evil.example.com",
    "npm install left-pad",
    "sudo launchctl load x.plist",
    "cat .env",                       # block-secrets veto
    "echo $ANTHROPIC_API_KEY",        # block-secrets veto
    "cat _local-only/secrets/.env",   # block-secrets veto
    "find . -name '*.md' -delete",    # block-secrets veto (distruttivo)
]

for c in ALLOW:
    check(aa.decide(c) == "allow", f"AUTO-APPROVA: {c}")
for c in GATE:
    check(aa.decide(c) is None, f"GATE (chiede/blocca): {c}")

passed = sum(1 for ok, _ in results if ok)
total = len(results)
print(f"\n{passed}/{total} test passati")
sys.exit(0 if passed == total else 1)
