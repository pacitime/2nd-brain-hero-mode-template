# 2nd Brain Hero Mode · Copyright (c) 2026 Alessandro Pacifico (Pacibrand).
# Vedi LICENZA.md nella radice del vault.
"""
drafts.py: ciclo di vita delle bozze preparate dall'assistente.

Le bozze che l'assistente prepara vivono in drafts/active/ (mai inviate in autonomia: l'invio lo
fa l'utente a mano). Questo modulo applica la regola dello SCADERE: una bozza ferma in active/
da piu' di 24h e' probabilmente fuori contesto -> si sposta in drafts/expired/ (cestino morbido).

  active/  -> (l'utente invia a mano, sposta lui)   -> sent/
  active/  -> (>24h non toccata, AUTOMATICO)        -> expired/

L'eta' si legge dal timestamp nel NOME file (AAAA-MM-GG-HHMM-...); se il nome non e' parsabile,
si ripiega sull'mtime del file. Spostando, aggiorna la riga '**Stato:**' a expired.

NB: qui NON si tocca active->sent (e' un gesto umano: e' l'utente a decidere cosa ha spedito).

Uso libreria:
    from drafts import expire_stale_drafts
    moved = expire_stale_drafts(root, now=..., dry_run=False)   # lista dei nomi scaduti

Agganciato all'heartbeat: a ogni /heartbeat le bozze vecchie scadono da sole (dry_run in preview).
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from shared import read_text, write_text_atomic  # noqa: E402

MAX_AGE_HOURS = 24
_TS_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})-(\d{2})(\d{2})")


def draft_age_hours(name: str, now: datetime) -> float | None:
    """Eta' in ore dal timestamp nel nome file, o None se il nome non e' parsabile."""
    m = _TS_RE.match(name)
    if not m:
        return None
    try:
        y, mo, d, hh, mm = (int(x) for x in m.groups())
        created = datetime(y, mo, d, hh, mm)
    except ValueError:
        return None
    return (now - created).total_seconds() / 3600.0


def _mark_expired(text: str) -> str:
    return re.sub(r"(\*\*Stato:\*\*\s*)(active|attiva)", r"\1expired", text, flags=re.IGNORECASE)


def expire_stale_drafts(root: Path, now: datetime | None = None,
                        max_age_hours: float = MAX_AGE_HOURS, dry_run: bool = False) -> list[str]:
    """Sposta le bozze di active/ piu' vecchie di max_age_hours in expired/. Ritorna i nomi.
    dry_run=True: elenca cosa scadrebbe senza spostare nulla (per la preview dell'heartbeat)."""
    now = now or datetime.now()
    active = root / "drafts" / "active"
    expired = root / "drafts" / "expired"
    moved: list[str] = []
    if not active.exists():
        return moved
    for p in sorted(active.glob("*.md")):
        age = draft_age_hours(p.name, now)
        if age is None:  # nome non standard: ripiega sull'mtime
            try:
                age = (now.timestamp() - p.stat().st_mtime) / 3600.0
            except OSError:
                continue
        if age <= max_age_hours:
            continue
        moved.append(p.name)
        if dry_run:
            continue
        expired.mkdir(parents=True, exist_ok=True)
        write_text_atomic(expired / p.name, _mark_expired(read_text(p)))
        try:
            p.unlink()
        except OSError:
            pass
    return moved
