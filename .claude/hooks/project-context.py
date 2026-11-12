# 2nd Brain Hero Mode · Copyright (c) 2026 Alessandro Pacifico (Pacibrand).
# Vedi LICENZA.md nella radice del vault.
"""
Hook UserPromptSubmit: quando un messaggio nomina un progetto, ne carica da solo il contesto.

PERCHE'. Senza questo hook il contesto di un progetto entra solo se l'utente chiede «prime su
<progetto>». Con l'hook basta nominarlo: alla prima menzione nella sessione l'assistente riceve
  - il metodo del progetto (`references/metodo.md`): come si lavora li';
  - gli essenziali di `references/`, interi, entro un tetto (oltre: solo i nomi dei file);
  - i titoli dei loop aperti del README (non il testo intero, che puo' essere lunghissimo);
  - l'elenco delle skill del progetto (`<progetto>/skills/<nome>/SKILL.md`).

Una sola volta per progetto per sessione (stato in `.claude/data/contesto-progetto/`). Tace per
i Claude di servizio (flush, giro posta, guard). Esce sempre con 0: un errore qui non deve mai
fermare un messaggio.

I progetti e i loro nomi vengono da `.claude/config/brain.json`: `path` e' la cartella, `alias`
la lista dei nomi con cui l'utente li chiama (assente: vale l'id). Si riconoscono solo come
parole intere. Le parole chiave dello smistamento delle call non si usano qui: sono pensate per
riconoscere un testo lungo, in un messaggio breve farebbero scattare progetti a caso.

Prova a mano (in una build di prova, non nel vault vero):
    echo '{"prompt":"dove siamo su progetto esempio?","session_id":"prova"}' | python3 project-context.py
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
STATO = ROOT / ".claude" / "data" / "contesto-progetto"
SERVIZIO = {"flush", "mail-sync", "guard"}

MAX_LOOP = 15          # titoli di loop mostrati per progetto
MAX_TITOLO = 170       # caratteri per titolo
MAX_METODO = 12000     # caratteri del metodo (circa 120 righe)
MAX_REFERENCES = 16000  # caratteri degli essenziali per progetto, metodo escluso
PRIORITA_REF = ["essenziali.md", "brand.md"]  # questi entrano per primi
ESCLUSI_REF = {"metodo.md", "_README.md"}


# ---------------------------------------------------------------------------
# Progetti dalla configurazione
# ---------------------------------------------------------------------------

def progetti() -> dict[str, tuple[str, list[str]]]:
    """id -> (cartella relativa, alias). Configurazione assente o rotta: nessun progetto."""
    try:
        sys.path.insert(0, str(ROOT / ".claude" / "scripts"))
        import brain_config
        dichiarati = brain_config.projects(ROOT)
    except Exception:
        return {}
    out = {}
    for p in dichiarati:
        alias = [a for a in (p.get("alias") or [p["id"]]) if isinstance(a, str) and a.strip()]
        out[p["id"]] = (p["path"], [a.strip() for a in alias])
    return out


def _regola(alias: str) -> re.Pattern[str]:
    return re.compile(r"(?<![\w-])" + re.escape(alias) + r"(?![\w-])", re.IGNORECASE)


def progetti_nominati(testo: str, mappa: dict[str, tuple[str, list[str]]] | None = None) -> list[str]:
    """Progetti nominati nel testo, nell'ordine in cui compaiono la prima volta."""
    mappa = progetti() if mappa is None else mappa
    trovati = []
    for pid, (_, alias) in mappa.items():
        posizioni = [m.start() for a in alias for m in [_regola(a).search(testo)] if m]
        if posizioni:
            trovati.append((min(posizioni), pid))
    return [pid for _, pid in sorted(trovati)]


# ---------------------------------------------------------------------------
# Pezzi del contesto
# ---------------------------------------------------------------------------

def _leggi(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""


def titoli_loop(readme: str) -> tuple[list[str], int]:
    """Titoli dei loop aperti nella sezione «Loop aperti» del README, e quanti sono in tutto."""
    m = re.search(r"^##[^\n]*[Ll]oop aperti[^\n]*\n(.*?)(?=^## |\Z)", readme, re.M | re.S)
    if not m:
        return [], 0
    titoli = []
    for riga in m.group(1).splitlines():
        if not riga.startswith("- [ ]"):
            continue
        urgente = "🔴" in riga[:20]
        grassetto = re.search(r"\*\*(.+?)\*\*", riga)
        t = grassetto.group(1) if grassetto else riga[5:]
        t = re.sub(r"\s+", " ", t).strip()
        if len(t) > MAX_TITOLO:
            t = t[: MAX_TITOLO - 1].rstrip() + "…"
        titoli.append(("🔴 " if urgente else "") + t)
    titoli.sort(key=lambda s: 0 if s.startswith("🔴") else 1)  # gli urgenti prima
    return titoli[:MAX_LOOP], len(titoli)


def skill_del_progetto(base: Path) -> list[str]:
    cartella = base / "skills"
    if not cartella.is_dir():
        return []
    return sorted(p.name for p in cartella.iterdir() if (p / "SKILL.md").is_file())


def essenziali(base: Path) -> tuple[list[tuple[str, str]], list[str]]:
    """(file caricati con il testo, file rimasti fuori dal tetto). Prima quelli prioritari,
    poi i piu' corti: cosi' il tetto lascia fuori un file lungo e non tre corti."""
    ref = base / "references"
    if not ref.is_dir():
        return [], []
    files = [p for p in ref.glob("*.md") if p.name not in ESCLUSI_REF]
    files.sort(key=lambda p: (PRIORITA_REF.index(p.name) if p.name in PRIORITA_REF else 9,
                              p.stat().st_size, p.name))
    caricati, rimasti, usati = [], [], 0
    for p in files:
        testo = _leggi(p)
        if usati + len(testo) <= MAX_REFERENCES:
            caricati.append((p.name, testo))
            usati += len(testo)
        else:
            rimasti.append(p.name)
    return caricati, sorted(rimasti)


def contesto(pid: str, cartella: str) -> str:
    base = ROOT / cartella
    if not base.is_dir():
        return ""
    parti = [f"## Contesto del progetto `{cartella}` (caricato da solo: l'utente l'ha nominato)"]

    metodo = _leggi(base / "references" / "metodo.md")
    if metodo:
        if len(metodo) > MAX_METODO:
            metodo = metodo[:MAX_METODO].rstrip() + "\n\n[...metodo troncato: aprilo per il resto]"
        parti.append("### Come lavoriamo qui (`references/metodo.md`)\n" + metodo)
    else:
        parti.append("_Il progetto non ha ancora `references/metodo.md`._")

    titoli, totale = titoli_loop(_leggi(base / "README.md"))
    if titoli:
        righe = "\n".join(f"- {t}" for t in titoli)
        coda = f"\n_({totale - len(titoli)} altri nel README.)_" if totale > len(titoli) else ""
        parti.append(f"### Loop aperti ({totale}, solo i titoli: il dettaglio è nel README)\n{righe}{coda}")

    caricati, rimasti = essenziali(base)
    for nome, testo in caricati:
        parti.append(f"### Essenziale: `references/{nome}`\n{testo}")
    if rimasti:
        parti.append("### Altri essenziali (aprili quando servono)\n"
                     + ", ".join(f"`references/{n}`" for n in rimasti))

    skill = skill_del_progetto(base)
    if skill:
        parti.append("### Skill del progetto\n" + ", ".join(f"`{s}`" for s in skill))

    return "\n\n".join(parti)


# ---------------------------------------------------------------------------
# Una volta per sessione
# ---------------------------------------------------------------------------

def gia_caricati(sessione: str) -> set[str]:
    try:
        return set(json.loads((STATO / f"{sessione}.json").read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError):
        return set()


def segna(sessione: str, fatti: set[str]) -> None:
    try:
        STATO.mkdir(parents=True, exist_ok=True)
        tmp = STATO / f".{sessione}.json.tmp"
        tmp.write_text(json.dumps(sorted(fatti)), encoding="utf-8")
        os.replace(tmp, STATO / f"{sessione}.json")
    except OSError:
        pass


def main() -> None:
    if os.environ.get("CLAUDE_INVOKED_BY") in SERVIZIO:
        return
    try:
        dati = json.load(sys.stdin)
    except ValueError:
        return
    if not isinstance(dati, dict):
        return
    testo = str(dati.get("prompt") or "")
    sessione = re.sub(r"[^A-Za-z0-9_-]", "", str(dati.get("session_id") or "senza-sessione"))[:80]
    sessione = sessione or "senza-sessione"
    mappa = progetti()
    nominati = progetti_nominati(testo, mappa)
    if not nominati:
        return
    fatti = gia_caricati(sessione)
    nuovi = [p for p in nominati if p not in fatti]
    blocchi = [c for c in (contesto(p, mappa[p][0]) for p in nuovi) if c]
    if not blocchi:
        return
    segna(sessione, fatti | set(nuovi))
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext": "\n\n---\n\n".join(blocchi),
    }}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception:  # un errore qui non deve mai bloccare un messaggio
        pass
    sys.exit(0)
