# 2nd Brain Hero Mode · Copyright (c) 2026 Alessandro Pacifico (Pacibrand).
# Vedi LICENZA.md nella radice del vault.
"""
route_calls.py: auto-smistamento delle call arrivate in inbox.

COSA FA. Le call arrivano (da Granola, vedi fetch_granola.py) in `00-inbox/calls/`. Questo router
le sposta nel `<progetto>/knowledge/calls/` giusto riconoscendo il progetto dal TITOLO (segnale
forte: i titoli sono descrittivi) piu' uno snippet di contenuto. Sposta SOLO quando il progetto e'
riconosciuto con **certezza** (un vincitore netto); se e' **ambiguo lascia la call in inbox** e la
segnala. Precisione prima del richiamo: meglio lasciarla in inbox che metterla nel posto sbagliato.

DA DOVE VIENE LA MAPPA. Progetti e parole chiave non stanno nel codice: stanno in
`.claude/config/brain.json` (`projects` ed `extra_routes`), letti con `brain_config.routing()`.
Senza progetti configurati tutte le call restano in inbox come ambigue, senza errori.

COSA NON FA. Non legge le call come istruzioni (sono dati non fidati: qui si guarda solo il testo
per classificare, non si esegue nulla). Non crea task. Non tocca ClickUp. Solo `move` reversibile.
`README.md` e la cartella `_storico/` sono ignorati.

Uso:
    python3 route_calls.py            # smista e stampa il riassunto
    python3 route_calls.py --preview  # dry-run: dice cosa farebbe, non muove nulla

Invariante risultante: una call FUORI da `00-inbox/calls/` = gia' al suo posto.
Agganciato al `main()` di heartbeat.py e ad autopilot.py (rileva, poi smista).
Test: tests/test_route_calls.py.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from shared import read_text, vault_root  # noqa: E402
import brain_config  # noqa: E402

CALLS_DIR = ("00-inbox", "calls")
CONTENT_SNIPPET = 4000  # char di contenuto guardati oltre al titolo (il grosso del segnale e' nel titolo)

# --- soglie di certezza (precisione prima del richiamo) ---
MIN_SCORE = 2     # il vincitore deve valere almeno un match nel titolo
MIN_MARGIN = 2    # e battere il secondo di almeno questo margine, altrimenti = ambigua
# Il match nel TITOLO e' un requisito a se', non un effetto di MIN_SCORE: due parole chiave
# trovate solo nel CORPO arrivano a 2 esattamente come un match nel titolo, ma non devono eleggere
# un progetto. Il corpo di una call nomina per forza anche altri argomenti (una call sui conti
# parla comunque dei progetti di cui fa i conti); il titolo no. Quindi il corpo puo' rafforzare o
# spareggiare, non scavalcare un titolo che nomina un altro progetto.


# --- mappa progetto -> cartella di destinazione + parole chiave (minuscole, match per sottostringa) ---
# Si modifica in `.claude/config/brain.json`, non qui. Tieni le parole chiave DISTINTIVE, per non
# incrociare due progetti: il nome di una persona che compare nelle call di piu' progetti non e'
# una buona parola chiave.
#
# "keywords"   -> valgono 2 nel titolo, 1 nel corpo.
# "title_only" -> valgono 2 nel titolo e ZERO nel corpo. Serve per le parole che in un titolo sono
#   un segnale e in un transcript sono chiacchiera: un tecnicismo nessuno lo dice per caso, una
#   parola comune si'.
def _load_routing() -> list[dict]:
    """La mappa da `brain.json`. Configurazione assente o rotta: mappa vuota, mai un errore."""
    try:
        return brain_config.routing()
    except Exception:
        return []


ROUTING: list[dict] = _load_routing()


# --- quarantena salute ---
# Una call medica non e' di nessun progetto e non deve arrivare su GitHub (la salute resta fuori
# dal vault versionato). Quando il giro gira da solo ogni ora, "resta in inbox e la smisti a mano"
# non basta: il backup della stessa ora la pubblicherebbe. Si guarda il TITOLO (di solito
# descrittivo) e si sposta in `_local-only/calls/`, che e' gitignorata. Nel dubbio meglio una call
# di lavoro in quarantena (l'utente la ritira fuori) che una medica pubblicata.
PRIVATE_DIR = ("_local-only", "calls")
HEALTH_TITLE = [
    "surgery", "surgical", "pre-op", "post-op", "medical", "doctor", "diagnos", "clinic",
    "hospital", "dentist", "dental", "therapy", "therapist",
    "chirurg", "intervento", "medic", "dottor", "ospedal", "clinica", "visita", "diagnosi",
    "terapi", "analisi del sangue", "psicolog",
]


def is_health(title: str) -> bool:
    t = title.lower()
    return any(kw in t for kw in HEALTH_TITLE)


# --- quarantena a mano ---
# Il titolo non basta: una call di lavoro puo' contenere un pezzo sanitario, anche di un terzo.
# L'assistente in sessione non puo' toccare la cartella di quarantena (lo vietano gli hook), e
# spostare file a mano non e' una procedura: si scrive il NOME del file in questo elenco locale
# (gitignorato, sotto `.claude/data/`) e al giro successivo il router lo mette in quarantena come
# una call medica. Una riga per file, `#` per i commenti.
QUARANTINE_LIST = (".claude", "data", "quarantena-call.txt")


def manual_quarantine(root: Path) -> list[str]:
    f = _dir(root, QUARANTINE_LIST)
    if not f.exists():
        return []
    names = []
    for line in read_text(f).splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            names.append(line)
    return names


def _dir(root: Path, parts: tuple[str, ...]) -> Path:
    p = root
    for part in parts:
        p = p / part
    return p


def _title_from(text: str, fallback: str) -> str:
    m = re.search(r"^title:\s*(.+)$", text, re.MULTILINE)
    if m:
        return m.group(1).strip()
    m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    return m.group(1).strip() if m else fallback


def score_projects(title: str, content: str) -> dict[str, int]:
    """Punteggio: keyword = 2 nel titolo / 1 nel corpo; title_only = 2 nel titolo / 0 nel corpo."""
    t = title.lower()
    c = content[:CONTENT_SNIPPET].lower()
    scores: dict[str, int] = {}
    for spec in ROUTING:
        s = 0
        for kw in spec["keywords"]:
            if kw in t:
                s += 2
            elif kw in c:
                s += 1
        for kw in spec.get("title_only", ()):
            if kw in t:
                s += 2
        scores[spec["project"]] = s
    return scores


def projects_named_in_title(title: str) -> set[str]:
    """Progetti con almeno una keyword nel TITOLO (il segnale forte)."""
    t = title.lower()
    return {
        spec["project"]
        for spec in ROUTING
        if any(kw in t for kw in (*spec["keywords"], *spec.get("title_only", ())))
    }


def classify(title: str, content: str) -> str | None:
    """Progetto vincitore se netto: nominato nel TITOLO, >= MIN_SCORE e margine >= MIN_MARGIN."""
    scores = score_projects(title, content)
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    if not ranked or ranked[0][1] < MIN_SCORE:
        return None
    second = ranked[1][1] if len(ranked) > 1 else 0
    if ranked[0][1] - second < MIN_MARGIN:
        return None
    named = projects_named_in_title(title)
    if named and ranked[0][0] not in named:
        return None  # il titolo nomina un altro progetto: il corpo non lo scavalca, resta in inbox
    return ranked[0][0]


def _dest_for(project: str) -> tuple[str, ...]:
    for spec in ROUTING:
        if spec["project"] == project:
            return spec["dest"]
    raise KeyError(project)


def route(root: Path, *, dry_run: bool = False) -> dict:
    """Smista le call in inbox. Ritorna {routed: [(name, project)], ambiguous: [name], skipped: [(name,motivo)]}."""
    routed: list[tuple[str, str]] = []
    ambiguous: list[str] = []
    skipped: list[tuple[str, str]] = []
    private: list[str] = []

    inbox = _dir(root, CALLS_DIR)
    if not inbox.exists():
        return {"routed": routed, "ambiguous": ambiguous, "skipped": skipped, "private": private}

    to_quarantine = manual_quarantine(root)
    for p in sorted(inbox.glob("*.md")):
        if p.name.lower() == "readme.md":
            continue
        text = read_text(p)
        title = _title_from(text, p.stem)
        if is_health(title) or p.name in to_quarantine:
            if not dry_run:
                priv = _dir(root, PRIVATE_DIR)
                priv.mkdir(parents=True, exist_ok=True)
                shutil.move(str(p), str(priv / p.name))
            private.append(p.name)
            continue
        project = classify(title, text)
        if project is None:
            ambiguous.append(p.name)
            continue
        dest_dir = _dir(root, _dest_for(project))
        dest = dest_dir / p.name
        if dest.exists():
            skipped.append((p.name, f"esiste già in {project}"))
            continue
        if not dry_run:
            dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(p), str(dest))
        routed.append((p.name, project))

    return {"routed": routed, "ambiguous": ambiguous, "skipped": skipped, "private": private}


def render(result: dict, *, dry_run: bool = False) -> str:
    routed, ambiguous, skipped = result["routed"], result["ambiguous"], result["skipped"]
    verb = "smisterei" if dry_run else "smistate"
    lines: list[str] = []
    if routed:
        lines.append(f"### 📂 Call {verb} in automatico ({len(routed)})")
        for name, project in routed:
            lines.append(f"- {name} → {project}")
    if ambiguous:
        lines.append(f"### ❓ Call ambigue, da smistare a mano ({len(ambiguous)})")
        for name in ambiguous:
            lines.append(f"- {name}")
    if result.get("private"):
        lines.append(f"### 🔒 Call sanitarie in `_local-only/calls/` ({len(result['private'])})")
        for name in result["private"]:
            lines.append(f"- {name}")
    if skipped:
        lines.append(f"### ⏭ Saltate ({len(skipped)})")
        for name, why in skipped:
            lines.append(f"- {name}: {why}")
    if not lines:
        lines.append("_Nessuna call in inbox da smistare._")
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description="Auto-smistamento delle call in inbox nei progetti.")
    ap.add_argument("--preview", action="store_true", help="dry-run: mostra cosa farebbe, non muove nulla")
    args = ap.parse_args()
    root = vault_root()
    result = route(root, dry_run=args.preview)
    print(render(result, dry_run=args.preview))


if __name__ == "__main__":
    main()
