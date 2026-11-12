# 2nd Brain Hero Mode · Copyright (c) 2026 Alessandro Pacifico (Pacibrand).
# Vedi LICENZA.md nella radice del vault.
"""
fetch_granola.py: ponte da Granola al vault, via API pubblica ufficiale.

PERCHE' L'API. Leggere le credenziali dai file locali dell'app Granola (come fanno alcuni plugin)
si rompe quando l'app cambia il modo in cui le conserva. L'**API pubblica ufficiale** (chiave
`grn_...`) e' un contratto stabile e non si rompe agli aggiornamenti.

COSA FA. Scarica le note (con il transcript) da `public-api.granola.ai` e le scrive come markdown
in `00-inbox/calls/`, un file per call: frontmatter (`granola_id`, `title`, `granola_url`,
`created_at`, `updated_at`), il riassunto e la sezione `## Transcript`. Da li' le smista
`route_calls.py`. Idempotente: rilanciarlo non riscarica e non duplica.

COSA NON FA. Non legge le call come istruzioni (dati NON fidati: qui si scrive soltanto).
Non tocca ClickUp, non crea task, non cancella nulla. Non stampa mai la chiave API.

CHIAVE. Variabile `GRANOLA_API_KEY`. La cerca prima nell'ambiente del processo, poi nel file
`_local-only/secrets/.env` del vault (gitignorato), alla riga `GRANOLA_API_KEY=grn_...`.
Senza chiave lo script esce con un messaggio e non fa nulla; dentro heartbeat e autopilot lo
scarico viene semplicemente saltato.

STATO DI SINCRONIA. `.claude/data/granola/synced.json`: l'elenco degli id Granola gia' scaricati
(id, titolo e nome file: nessun segreto). In piu' una call non viene riscaricata se un file con
lo stesso nome esiste gia' in una cartella `calls/` del vault.

Uso:
    python3 fetch_granola.py                  # scarica le nuove note
    python3 fetch_granola.py --preview        # dry-run: dice cosa scaricherebbe
    python3 fetch_granola.py --since AAAA-MM-GG   # backfill da una data
    python3 fetch_granola.py --probe          # ispeziona lo schema API (nessuna scrittura)

Invariante a valle: una call in `00-inbox/calls/` = ancora da smistare (ci pensa route_calls).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from shared import vault_root, write_text_atomic  # noqa: E402

API_BASE = "https://public-api.granola.ai/v1"
CALLS_DIR = ("00-inbox", "calls")
STATE_PATH = (".claude", "data", "granola", "synced.json")
ENV_KEY = "GRANOLA_API_KEY"

# rate limit dichiarato: 5 req/s sostenuti, burst 25. Stiamo sotto con margine.
RATE_SLEEP = 0.25
PAGE_LIMIT = 100
MAX_PAGES = 50  # guardia anti-loop sulla paginazione


# --------------------------------------------------------------------------- chiave

def load_key(root: Path) -> str | None:
    """Chiave da env, altrimenti dal file secrets. Non viene MAI stampata né loggata."""
    from_env = os.environ.get(ENV_KEY)
    if from_env and from_env.strip():
        return from_env.strip()
    secrets_file = root / "_local-only" / "secrets" / ".env"
    if not secrets_file.exists():
        return None
    try:
        lines = secrets_file.read_text(encoding="utf-8").splitlines()
    except Exception:
        return None
    prefix = ENV_KEY + "="
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(prefix):
            return stripped[len(prefix):].strip().strip('"').strip("'")
    return None


# --------------------------------------------------------------------------- API

class ApiError(RuntimeError):
    pass


def api_get(path: str, key: str, params: dict | None = None) -> dict:
    url = API_BASE + path
    if params:
        url = url + "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    request = urllib.request.Request(url)
    request.add_header("Authorization", "Bearer " + key)
    request.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8")[:400]
        except Exception:
            pass
        raise ApiError(f"HTTP {e.code} su {path}: {body}") from None
    except urllib.error.URLError as e:
        raise ApiError(f"rete non raggiungibile su {path}: {e.reason}") from None


def iter_notes(key: str, since: str | None) -> list[dict]:
    """Elenca le note, seguendo la paginazione a cursore."""
    out: list[dict] = []
    cursor = None
    for _ in range(MAX_PAGES):
        params = {"limit": PAGE_LIMIT}
        if since:
            params["created_after"] = since
        if cursor:
            params["cursor"] = cursor
        payload = api_get("/notes", key, params)
        batch = payload.get("notes") or payload.get("data") or payload.get("items") or []
        out.extend(batch)
        cursor = payload.get("cursor") or payload.get("next_cursor")
        if not payload.get("hasMore") or not cursor or not batch:
            break
        time.sleep(RATE_SLEEP)
    return out


def fetch_note(note_id: str, key: str) -> dict:
    payload = api_get(f"/notes/{note_id}", key, {"include": "transcript"})
    return payload.get("data") or payload


# --------------------------------------------------------------------------- rendering

def _pick(d: dict, *names, default=""):
    for n in names:
        v = d.get(n)
        if v:
            return v
    return default


def safe_filename(created_at: str, title: str) -> str:
    """Convenzione dei nomi: {data di creazione}-{titolo}, spazi → '-'. Deterministica."""
    date = (created_at or "")[:10] or "0000-00-00"
    clean = (title or "senza-titolo").strip()
    clean = clean.replace("/", "-").replace("\\", "-").replace(":", "-")
    clean = re.sub(r"\s+", "-", clean)
    clean = re.sub(r"-{3,}", "--", clean).strip("-")
    return f"{date}-{clean}"[:180] + ".md"


def _who(speaker) -> str:
    """L'API dà `{'source': 'microphone', 'attribution': 'me'}`, non una stringa.

    Per chi è in call da remoto c'è quasi sempre anche `name` (il nome che ha nella call,
    es. 'Mario Rossi'): si scrive quello. "Them" resta solo per i blocchi che Granola non
    ha attribuito.
    """
    if isinstance(speaker, dict):
        tag = str(speaker.get("attribution") or speaker.get("source") or "").lower()
        name = str(speaker.get("name") or "").strip()
    else:
        tag = str(speaker or "").lower()
        name = ""
    if tag in ("me", "self", "microphone", "mic", "user"):
        return "Me"
    return name or "Them"


def _clock(stamp) -> str:
    """`start_time` è ISO in UTC: si mostra in ora locale."""
    if isinstance(stamp, (int, float)):
        total = int(stamp if stamp < 100000 else stamp / 1000)
        return f"{total // 3600:02d}:{(total % 3600) // 60:02d}:{total % 60:02d}"
    if not isinstance(stamp, str) or "T" not in stamp:
        return ""
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        return dt.astimezone().strftime("%H:%M:%S")
    except Exception:
        return stamp[11:19]


def render_transcript(segments: list) -> str:
    """Una riga per intervento: `**Chi** *(HH:MM:SS)*: testo`."""
    lines: list[str] = []
    for seg in segments or []:
        if not isinstance(seg, dict):
            continue
        text = _pick(seg, "text", "content", "transcript")
        if not text:
            continue
        clock = _clock(_pick(seg, "start_time", "start_timestamp", "timestamp", "start"))
        head = f"**{_who(seg.get('speaker'))}**" + (f" *({clock})*" if clock else "")
        lines.append(f"{head}: {str(text).strip()}")
    return "\n\n".join(lines)


def render_note(note: dict) -> tuple[str, str]:
    """Ritorna (nome_file, contenuto markdown). Il formato lo leggono route_calls e heartbeat."""
    note_id = _pick(note, "id", "note_id", "document_id")
    title = _pick(note, "title", "name", default="Senza titolo")
    created = _pick(note, "created_at", "createdAt")
    updated = _pick(note, "updated_at", "updatedAt", default=created)
    body = _pick(note, "summary_markdown", "content_markdown", "markdown", "content",
                 "notes_markdown", "enhanced_notes", "summary_text")
    if isinstance(body, dict):
        body = _pick(body, "markdown", "text", default="")
    web_url = _pick(note, "web_url", default=f"https://notes.granola.ai/d/{note_id}")

    parts = [
        "---",
        f"granola_id: {note_id}",
        f"title: {title}",
        f"granola_url: {web_url}",
        f"created_at: {created}",
        f"updated_at: {updated}",
        "tags: []",
        "---",
        "",
        f"# {title}",
        "",
        str(body).strip(),
        "",
    ]

    segments = note.get("transcript") or note.get("transcript_segments") or []
    if isinstance(segments, dict):
        segments = segments.get("segments") or segments.get("data") or []
    body_transcript = render_transcript(segments) if isinstance(segments, list) else ""
    if body_transcript:
        parts += ["## Transcript", "", body_transcript, ""]

    return safe_filename(created, title), "\n".join(parts)


# --------------------------------------------------------------------------- stato

def _state_file(root: Path) -> Path:
    p = root
    for part in STATE_PATH:
        p = p / part
    return p


def load_state(root: Path) -> dict:
    f = _state_file(root)
    if not f.exists():
        return {"synced": {}}
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return {"synced": {}}


def save_state(root: Path, state: dict) -> None:
    f = _state_file(root)
    f.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(f, json.dumps(state, indent=2, ensure_ascii=False))


# --------------------------------------------------------------------------- sync

def existing_call_files(root: Path) -> set[str]:
    """
    Nomi dei file di call gia' presenti nel vault (inbox, _storico e tutti i
    `knowledge/calls/` dei progetti).

    Il dedup e' anche sul NOME FILE, non solo sull'id: una call portata nel vault per
    un'altra strada (a mano, o con un altro strumento che usa id diversi da quelli
    dell'API pubblica) non verrebbe riconosciuta dall'id. Il nome file invece e'
    deterministico (`{data}-{titolo}`).
    """
    names: set[str] = set()
    for base in (root / "00-inbox", root / "10-lavoro", root / "20-fiscale-legale",
                 root / "30-personale"):
        if not base.exists():
            continue
        for calls_dir in base.rglob("calls"):
            if not calls_dir.is_dir():
                continue
            # rglob e non glob: prende anche le sottocartelle, es. `00-inbox/calls/_storico/`.
            for p in calls_dir.rglob("*.md"):
                names.add(p.name)
    return names


def sync(root: Path, key: str, *, since: str | None, dry_run: bool) -> dict:
    state = load_state(root)
    synced: dict = state.setdefault("synced", {})

    notes = iter_notes(key, since)
    on_disk = existing_call_files(root)
    written: list[str] = []
    skipped: list[str] = []

    inbox = root
    for part in CALLS_DIR:
        inbox = inbox / part

    for meta in notes:
        note_id = _pick(meta, "id", "note_id", "document_id")
        if not note_id:
            continue
        title = _pick(meta, "title", default="Senza titolo")
        if note_id in synced:
            skipped.append(f"{title}: già scaricata")
            continue

        # nome file calcolato PRIMA di scaricare il dettaglio: se la call c'è già,
        # si evita del tutto la chiamata API.
        filename = safe_filename(_pick(meta, "created_at", "createdAt"), title)
        if filename in on_disk:
            synced[note_id] = {"title": title, "status": "già nel vault", "file": filename}
            skipped.append(f"{filename}: già nel vault")
            continue

        if dry_run:
            written.append(f"{filename} (dry-run)")
            continue

        time.sleep(RATE_SLEEP)
        full = fetch_note(note_id, key)
        _, content = render_note({**meta, **full})

        inbox.mkdir(parents=True, exist_ok=True)
        write_text_atomic(inbox / filename, content)
        on_disk.add(filename)
        synced[note_id] = {"title": title, "file": filename}
        written.append(filename)

    if not dry_run:
        save_state(root, state)
    return {"written": written, "skipped": skipped, "total": len(notes)}


def sync_for_heartbeat(root: Path, *, days: int = 45, dry_run: bool = False) -> dict | None:
    """
    Entry point per heartbeat.py e autopilot.py: scarica solo la finestra recente e non
    alza MAI eccezioni. Se manca la chiave o la rete è giù torna None, e il giro va avanti.
    """
    from datetime import datetime, timedelta, timezone
    key = load_key(root)
    if not key:
        return None
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        return sync(root, key, since=since, dry_run=dry_run)
    except (ApiError, OSError):
        return None


def render_report(result: dict, *, dry_run: bool) -> str:
    verb = "scaricherei" if dry_run else "scaricate"
    lines = [f"### 🎙 Granola: {result['total']} note viste sull'API"]
    if result["written"]:
        lines.append(f"**Call {verb} ({len(result['written'])})** → `00-inbox/calls/`")
        for name in result["written"]:
            lines.append(f"- {name}")
    else:
        lines.append("_Nessuna call nuova._")
    if result["skipped"]:
        lines.append(f"\n<details><summary>Saltate ({len(result['skipped'])})</summary>\n")
        for name in result["skipped"][:40]:
            lines.append(f"- {name}")
        lines.append("\n</details>")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- probe

def probe(key: str) -> None:
    """Ispeziona lo schema dell'API senza scrivere niente. Non stampa la chiave."""
    payload = api_get("/notes", key, {"limit": 3})
    print("chiavi risposta /notes:", sorted(payload.keys()))
    batch = payload.get("data") or payload.get("notes") or payload.get("items") or []
    print("note in pagina:", len(batch))
    if not batch:
        print("nessuna nota restituita")
        return
    print("chiavi di una nota:", sorted(batch[0].keys()))
    note_id = _pick(batch[0], "id", "note_id", "document_id")
    print("titolo prima nota:", _pick(batch[0], "title", default="(senza titolo)"))
    detail = fetch_note(note_id, key)
    print("chiavi dettaglio:", sorted(detail.keys()))
    segs = detail.get("transcript") or detail.get("transcript_segments") or []
    if isinstance(segs, dict):
        print("transcript è un dict, chiavi:", sorted(segs.keys()))
        segs = segs.get("segments") or segs.get("data") or []
    if isinstance(segs, list) and segs:
        print("segmenti:", len(segs), "| chiavi segmento:", sorted(segs[0].keys()))
        speakers = sorted({str(s.get("speaker")) for s in segs if isinstance(s, dict)})
        print("valori distinti di 'speaker':", speakers)
        print("esempio start_time:", repr(segs[0].get("start_time")))
        print("summary_markdown presente:", bool(detail.get("summary_markdown")),
              "| lunghezza:", len(str(detail.get("summary_markdown") or "")))
        print("primo pezzo di summary_markdown:\n", str(detail.get("summary_markdown") or "")[:300])
    print("--- test filtro created_after ---")
    from datetime import datetime, timedelta, timezone
    since = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT00:00:00Z")
    recent = api_get("/notes", key, {"created_after": since})
    rb = recent.get("notes") or []
    print("note degli ultimi 30 giorni:", len(rb), "| hasMore:", recent.get("hasMore"))
    for n in rb[:15]:
        print("   ", str(n.get("created_at"))[:10], "|", n.get("title"))


def main() -> None:
    ap = argparse.ArgumentParser(description="Scarica le call Granola nel vault via API ufficiale.")
    ap.add_argument("--preview", action="store_true", help="dry-run: mostra cosa scaricherebbe")
    ap.add_argument("--since", help="scarica solo le note create dopo questa data (YYYY-MM-DD)")
    ap.add_argument("--probe", action="store_true", help="ispeziona lo schema API, non scrive nulla")
    args = ap.parse_args()

    root = vault_root()
    key = load_key(root)
    if not key:
        print(f"Granola non configurato: manca la chiave {ENV_KEY}.\n"
              f"Mettila in _local-only/secrets/.env, su una riga `{ENV_KEY}=grn_...`, "
              "oppure nell'ambiente. Finché manca non c'è niente da scaricare.", file=sys.stderr)
        sys.exit(1)

    try:
        if args.probe:
            probe(key)
            return
        result = sync(root, key, since=args.since, dry_run=args.preview)
        print(render_report(result, dry_run=args.preview))
    except ApiError as e:
        print(f"ERRORE API Granola: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
