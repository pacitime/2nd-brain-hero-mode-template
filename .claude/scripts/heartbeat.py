# 2nd Brain Hero Mode · Copyright (c) 2026 Alessandro Pacifico (Pacibrand).
# Vedi LICENZA.md nella radice del vault.
"""
heartbeat.py: il motore del briefing proattivo. Advisor a comando, non demone.

COSA FA (e cosa NO). Legge cio' che e' GIA' su disco nel vault, capisce COSA E' CAMBIATO
dall'ultimo giro, passa le novita' esterne dal guard-agent (guard_agent.py), e produce un
briefing-delta sicuro che l'assistente (in sessione) legge per PROPORRE. Non crea task, non
invia, non decide: e' un advisor.

EMAIL. Se il modulo posta e' acceso in `.claude/config/brain.json` (oggetto `mail`), la posta di
Apple Mail entra nel briefing DA SOLA: se il digest prodotto da `mail/daily.py` manca o e'
vecchio, il motore rilancia lui quello script (sola lettura) e ne ingoia il risultato come item
live. Non serve passare `--extra` a mano. Con il modulo spento (il default) il giro posta si
salta e lo dice in una riga.
Perche' qui e non da un job schedulato: launchd non ha "app responsabile", quindi macOS gli
nega le cartelle protette (Scrivania, Documenti) e un giro schedulato muore con 'Operation not
permitted' se il vault sta li'. In sessione i permessi ci sono, quindi la posta si legge quando
serve davvero: al briefing.
`--extra` resta e VINCE sull'automatismo (calendario, o un file costruito a mano).

PERCHE' IL DIFFING (l'anti-nagging). Se l'assistente leggesse i mirror da solo vedrebbe TUTTO
ogni volta e annoierebbe l'utente. Il motore salva uno snapshot in
`.claude/data/state/heartbeat-state.json` e al giro dopo emergono SOLO le novita' (nuove call,
nuove task, nuovi promemoria, cose sparite).

FONTI v1 (solo disco, zero token):
  - call non ancora smistate          -> 00-inbox/calls/*.md
  - task ClickUp assegnate (mirror)   -> 03-task/clickup-mirror/*.md   (id = cu:<id>)
  - promemoria Apple (mirror)         -> 03-task/reminders-mirror/*.md (chiave = nome)
  - loop aperti dei dossier           -> sezioni '🔓 Loop aperti' nei *.md del vault

LOOP APERTI (non e' un diff, e' un promemoria). I dossier hanno una sezione '🔓 Loop aperti'
con voci '- [ ]'. Non riemergono ogni volta (sarebbe nagging): compaiono solo quando il dossier
e' fermo da >= LOOP_STALE_DAYS giorni (la piu' recente fra 'aggiornato:' nel frontmatter e
l'ultimo commit git sul file; mtime solo se mancano entrambe).
Aggiornare il dossier = azzerare il timer. E' l'anti-nagging applicato allo stato, non al delta.

SICUREZZA. Le novita' esterne passano da guard_batch() (metal detector + buttafuori). Il verdetto
ANNOTA ogni item (ok / CAUTELA / QUARANTENA): per le call NON si nasconde l'esistenza (e' roba
dell'utente, la deve smistare lui) ma il contenuto quarantenato non va auto-processato senza revisione.

Uso:
    python3 heartbeat.py                 # stampa il briefing-delta e AGGIORNA lo stato
    python3 heartbeat.py --preview       # stampa senza salvare (dry-run)
    python3 heartbeat.py --reset         # azzera lo stato (il prossimo giro vede tutto "nuovo")
    python3 heartbeat.py --no-guard      # salta il buttafuori LLM (solo diffing; per test/veloce)
    python3 heartbeat.py --extra live.json   # item esterni espliciti (VINCE sull'auto-mail)
    python3 heartbeat.py --no-mail       # salta il giro email automatico
    python3 heartbeat.py --mail-fresh    # forza il refresh del digest anche se recente

Test: test_heartbeat.py, con vault finto in tmp e GUARD_AGENT_STUB (nessun token).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "mail"))
from shared import read_text, vault_root, write_text_atomic  # noqa: E402
import daily as mail_daily  # noqa: E402  (mail/daily.py: giro posta, sola lettura)
import guard_agent as ga  # noqa: E402
import route_calls as rc  # noqa: E402
import fetch_granola as fg  # noqa: E402
import health_check as hc  # noqa: E402  (invarianti del vault, sola lettura)
from drafts import expire_stale_drafts  # noqa: E402

# --- percorsi delle fonti (relativi alla root del vault) ---
CALLS_DIR = ("00-inbox", "calls")
CLICKUP_DIR = ("03-task", "clickup-mirror")
REMINDERS_DIR = ("03-task", "reminders-mirror")
STATE_REL = (".claude", "data", "state", "heartbeat-state.json")

# --- posta (digest fuori-git: contiene banca/legale/personale, vedi mail/daily.py) ---
MAIL_MAX_AGE_H = 6    # sotto questa eta' il digest si riusa; sopra, si rifa (Mail e' lenta)
MAIL_TIMEOUT_S = 75   # per-account: un account che non risponde non tiene in ostaggio il briefing

CALL_GUARD_CAP = 20_000  # char passati al guard per call (testa+coda: l'injection sta agli estremi)

_CU_RE = re.compile(r"<!--\s*cu:(\w+).*?(?:st:([^>]*?))?\s*-->")
_REM_RE = re.compile(r"<!--\s*rem-list:.*?-->")

# --- loop aperti: dossier con una sezione "🔓 Loop aperti" e voci non spuntate ---
LOOP_STALE_DAYS = 7  # soglia anti-nagging: un loop riemerge solo se il dossier e' fermo da >= N giorni
_LOOP_HEADING_RE = re.compile(r"^#{1,6}\s+.*loop aperti", re.IGNORECASE)
_LOOP_ITEM_RE = re.compile(r"^\s*-\s*\[ \]\s*(.+)$")
_HEADING_RE = re.compile(r"^#{1,6}\s")
_FM_DATE_RE = re.compile(r"^aggiornato:\s*(\d{4}-\d{2}-\d{2})", re.MULTILINE)
_H1_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
# top-level (o segmenti) da saltare nella scansione loop: infra, raw, ignorati, modelli
LOOP_SKIP = {".claude", ".git", ".obsidian", "node_modules", "_kit", "_local-only",
             "01-daily", "00-inbox", "_sources", "_TEMPLATE-progetto"}


# ============================================================
# utility
# ============================================================
def _hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def _task_text(line: str) -> str:
    """Estrae il testo umano di una riga-task: toglie checkbox, commento HTML e metadati."""
    s = re.sub(r"^\s*-\s*\[[ xX]\]\s*", "", line)
    s = re.sub(r"<!--.*?-->", "", s)
    s = re.split(r"\s+(?:📅|⏫|🔼|🔽|🔗|#)", s)[0]
    return s.strip()


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _dir(root: Path, parts: tuple[str, ...]) -> Path:
    p = root
    for part in parts:
        p = p / part
    return p


def state_path(root: Path) -> Path:
    return _dir(root, STATE_REL)


# ============================================================
# collettori (solo disco)
# ============================================================
def collect_calls(root: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    d = _dir(root, CALLS_DIR)
    if not d.exists():
        return out
    for p in sorted(d.glob("*.md")):
        if p.name.lower() == "readme.md":
            continue
        text = read_text(p)
        out[p.name] = {"title": p.stem, "hash": _hash(text), "content": text}
    return out


def collect_clickup(root: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    d = _dir(root, CLICKUP_DIR)
    if not d.exists():
        return out
    for p in sorted(d.glob("*.md")):
        for line in read_text(p).splitlines():
            m = _CU_RE.search(line)
            if not m:
                continue
            cid = m.group(1)
            state = (m.group(2) or "").strip()
            out[cid] = {"text": _task_text(line), "state": state, "file": p.stem}
    return out


def collect_reminders(root: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    d = _dir(root, REMINDERS_DIR)
    if not d.exists():
        return out
    for p in sorted(d.glob("*.md")):
        for line in read_text(p).splitlines():
            if not _REM_RE.search(line):
                continue
            text = _task_text(line)
            key = _norm(text)
            if key:
                out[key] = {"text": text}
    return out


def _extract_loops(text: str) -> list[str]:
    """Voci non spuntate (- [ ]) sotto una o piu' sezioni '🔓 Loop aperti', fino all'heading dopo."""
    items: list[str] = []
    in_section = False
    for line in text.splitlines():
        if _LOOP_HEADING_RE.match(line):
            in_section = True
            continue
        if in_section and _HEADING_RE.match(line):
            in_section = False
            continue
        if in_section:
            m = _LOOP_ITEM_RE.match(line)
            if m:
                items.append(m.group(1).strip())
    return items


def collect_dossier_senza_loop(root: Path) -> list[str]:
    """README di progetto SENZA la sezione '🔓 Loop aperti'.

    Invariante: la sezione deve esistere in ogni dossier di progetto, perche' e' la superficie
    che questo motore sorveglia e che le call riconciliano (CLAUDE §9). Un dossier senza
    sezione non e' 'senza loop': e' INVISIBILE al briefing, che e' peggio, perche' sembra a
    posto (per esempio un progetto che tiene le questioni aperte solo in MEMORY.md).

    Solo i dossier veri: un README che e' l'indice di una cartella-contenitore non ha loop
    propri, e segnalarlo genererebbe rumore permanente.
    """
    out: list[str] = []
    for p in sorted(root.rglob("README.md")):
        rel = p.relative_to(root)
        if any(part in LOOP_SKIP for part in rel.parts):
            continue
        if rel.parts[0] not in ("10-lavoro", "20-fiscale-legale", "30-personale"):
            continue
        # un dossier di progetto sta accanto al suo MEMORY.md o al suo knowledge/
        d = p.parent
        if not ((d / "MEMORY.md").exists() or (d / "knowledge").is_dir()):
            continue
        text = read_text(p)
        # i contenitori si dichiarano tali nel frontmatter: hanno knowledge condivisa
        # ma nessun loop proprio (es. una cartella che raggruppa i progetti di piu' clienti)
        if "tipo: contenitore" in text.lower():
            continue
        if "loop aperti" not in text.lower():
            out.append(rel.as_posix())
    return out


def _git_usable(root: Path) -> bool:
    """Vero se root e' un repo git con la cronologia completa.

    Su un clone shallow ogni file ha la data del clone: tutto sembrerebbe appena toccato e
    nessun loop risulterebbe mai fermo. Li' la data git non si usa."""
    try:
        r = subprocess.run(["git", "-C", str(root), "rev-parse", "--is-shallow-repository"],
                           capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0 and r.stdout.strip() == "false"


def _git_last_commit(root: Path, rel: Path) -> datetime | None:
    """Data dell'ultimo commit che ha toccato il file, o None.

    Perche': 'aggiornato:' lo aggiorna solo chi se ne ricorda. Una routine che aggiunge loop a
    un README senza toccare il frontmatter lo farebbe risultare 'fermo da settimane' la mattina
    dopo averlo modificato. Il commit non dimentica."""
    try:
        r = subprocess.run(["git", "-C", str(root), "log", "-1", "--format=%ct", "--", rel.as_posix()],
                           capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    ts = r.stdout.strip()
    return datetime.fromtimestamp(int(ts)) if r.returncode == 0 and ts.isdigit() else None


def collect_loops(root: Path, now: datetime | None = None) -> list[dict]:
    """Dossier del vault con loop aperti + eta' in giorni dall'ultima modifica nota.

    Ultima modifica = la piu' recente fra 'aggiornato:' e l'ultimo commit git; l'mtime solo se
    mancano entrambe. Non e' un diff: e' una vista di stato corrente (il promemoria 'ogni tanto')."""
    now = now or datetime.now()
    use_git = _git_usable(root)
    out: list[dict] = []
    for p in sorted(root.rglob("*.md")):
        rel = p.relative_to(root)
        if any(part in LOOP_SKIP for part in rel.parts):
            continue
        text = read_text(p)
        if "loop aperti" not in text.lower():
            continue
        items = _extract_loops(text)
        if not items:
            continue
        dates = []
        m = _FM_DATE_RE.search(text)
        if m:
            try:
                dates.append(datetime.strptime(m.group(1), "%Y-%m-%d"))
            except ValueError:
                pass
        if use_git:
            committed = _git_last_commit(root, rel)
            if committed:
                dates.append(committed)
        updated = max(dates) if dates else datetime.fromtimestamp(p.stat().st_mtime)
        h1 = _H1_RE.search(text)
        out.append({
            "file": rel.as_posix(),
            "title": (h1.group(1).strip() if h1 else rel.stem),
            "age": (now - updated).days,
            "items": items,
        })
    return out


def build_snapshot(root: Path, now: datetime | None = None) -> dict:
    return {
        "generated": (now or datetime.now()).isoformat(timespec="seconds"),
        "sources": {
            "calls": collect_calls(root),
            "clickup": collect_clickup(root),
            "reminders": collect_reminders(root),
        },
    }


# ============================================================
# stato (persistenza) + diff
# ============================================================
def _lean(snapshot: dict) -> dict:
    """Toglie il contenuto pesante delle call prima di salvare lo stato (tiene solo l'hash)."""
    src = snapshot["sources"]
    calls = {k: {"title": v["title"], "hash": v["hash"]} for k, v in src["calls"].items()}
    return {"generated": snapshot["generated"],
            "sources": {"calls": calls, "clickup": src["clickup"], "reminders": src["reminders"]}}


def load_state(root: Path) -> dict:
    p = state_path(root)
    if not p.exists():
        return {"calls": {}, "clickup": {}, "reminders": {}}
    try:
        return json.loads(read_text(p)).get("sources", {"calls": {}, "clickup": {}, "reminders": {}})
    except Exception:
        return {"calls": {}, "clickup": {}, "reminders": {}}


def save_state(root: Path, snapshot: dict) -> None:
    write_text_atomic(state_path(root), json.dumps(_lean(snapshot), ensure_ascii=False, indent=2))


def diff_source(old: dict, new: dict, change_key: str | None) -> dict:
    """added/removed/changed. `change_key` = campo da confrontare per 'changed' (hash o state)."""
    added = [k for k in new if k not in old]
    removed = [k for k in old if k not in new]
    changed = []
    if change_key:
        changed = [k for k in new if k in old and old[k].get(change_key) != new[k].get(change_key)]
    return {"added": added, "removed": removed, "changed": changed}


# ============================================================
# orchestrazione
# ============================================================
def _cap(text: str) -> str:
    if len(text) <= CALL_GUARD_CAP:
        return text
    head = CALL_GUARD_CAP * 4 // 5
    return text[:head] + "\n[...taglio heartbeat...]\n" + text[-(CALL_GUARD_CAP - head):]


def run_heartbeat(root: Path, *, save: bool = True, use_guard: bool = True,
                  extra_items: list[dict] | None = None, now: datetime | None = None) -> str:
    # Ciclo di vita bozze: le >24h scadono (dry-run in preview, così non muove file).
    expired_drafts = expire_stale_drafts(root, now=now, dry_run=not save)

    snap = build_snapshot(root, now=now)
    old = load_state(root)
    src = snap["sources"]

    d_calls = diff_source(old.get("calls", {}), src["calls"], "hash")
    d_cu = diff_source(old.get("clickup", {}), src["clickup"], "state")
    d_rem = diff_source(old.get("reminders", {}), src["reminders"], None)

    # --- costruisci il lotto per il guard: nuove/cambiate call + eventuali extra ---
    guard_items: list[dict] = []
    for name in d_calls["added"] + d_calls["changed"]:
        guard_items.append({"source": f"call:{name}", "content": _cap(src["calls"][name]["content"])})
    for it in (extra_items or []):
        guard_items.append({"source": it.get("source", "extra"), "content": it.get("content", "")})

    verdicts: dict[str, ga.GuardResult] = {}
    if use_guard and guard_items:
        for r in ga.guard_batch(guard_items):
            verdicts[r.source] = r

    def tag(source: str) -> str:
        r = verdicts.get(source)
        if not r:
            return ""
        return {"pass": "", "suspicious": "  ⚠️ CAUTELA", "fail": "  🚫 QUARANTENA (rivedi a mano)"}[r.verdict]

    loops = collect_loops(root, now=now)

    return _render(snap, d_calls, d_cu, d_rem, src, verdicts, tag, extra_items or [],
                   expired_drafts, loops, save, root)


def _render(snap, d_calls, d_cu, d_rem, src, verdicts, tag, extra_items, expired_drafts, loops, save, root) -> str:
    lines: list[str] = [f"## Heartbeat, {snap['generated']}  (novita' dall'ultimo giro)", ""]
    any_news = False

    if expired_drafts:
        any_news = True
        verb = "scadrebbero" if not save else "spostate in expired/"
        lines.append(f"### 🗑 Bozze scadute >24h ({len(expired_drafts)}): {verb}")
        for name in expired_drafts:
            lines.append(f"- {name}")
        lines.append("")

    new_calls = d_calls["added"] + d_calls["changed"]
    if new_calls:
        any_news = True
        lines.append(f"### 📞 Call da smistare ({len(new_calls)})")
        for name in new_calls:
            flag = " (aggiornata)" if name in d_calls["changed"] else ""
            lines.append(f"- {src['calls'][name]['title']}{flag}{tag(f'call:{name}')}")
        lines.append("")

    if d_cu["added"] or d_cu["changed"]:
        any_news = True
        lines.append(f"### ✅ Task ClickUp ({len(d_cu['added'])} nuove, {len(d_cu['changed'])} cambiate)")
        for cid in d_cu["added"]:
            t = src["clickup"][cid]
            lines.append(f"- {t['text']} · _st:{t['state']}_ · {t['file']}")
        for cid in d_cu["changed"]:
            t = src["clickup"][cid]
            lines.append(f"- (stato cambiato) {t['text']} → _st:{t['state']}_")
        lines.append("")

    if d_rem["added"]:
        any_news = True
        lines.append(f"### 📌 Promemoria nuovi ({len(d_rem['added'])})")
        for k in d_rem["added"]:
            lines.append(f"- {src['reminders'][k]['text']}")
        lines.append("")

    closed = d_cu["removed"] + d_rem["removed"]
    if closed:
        any_news = True
        lines.append(f"### ↩︎ Spariti dai mirror (chiusi/completati?) ({len(closed)})")
        for cid in d_cu["removed"]:
            lines.append(f"- [ClickUp] {old_text(root, 'clickup', cid)}")
        for k in d_rem["removed"]:
            lines.append(f"- [Promemoria] {k}")
        lines.append("")

    stale_loops = [d for d in (loops or []) if d["age"] >= LOOP_STALE_DAYS]
    if stale_loops:
        any_news = True
        total = sum(len(d["items"]) for d in stale_loops)
        lines.append(f"### 🔓 Loop aperti fermi ({total}): dossier non aggiornati da ≥{LOOP_STALE_DAYS}g")
        for d in sorted(stale_loops, key=lambda x: -x["age"]):
            lines.append(f"- **{d['title']}** _(fermo {d['age']}g)_ · {d['file']}")
            for it in d["items"]:
                lines.append(f"  - [ ] {it}")
        lines.append("")

    senza = collect_dossier_senza_loop(root)
    if senza:
        any_news = True
        lines.append(f"### ⚠️ Dossier senza sezione '🔓 Loop aperti' ({len(senza)}): invisibili al briefing")
        for f in senza:
            lines.append(f"- {f}")
        lines.append("")

    if extra_items:
        admitted = [it for it in extra_items
                    if verdicts.get(it.get('source', 'extra'), None) is None
                    or not verdicts[it['source']].quarantined]
        any_news = any_news or bool(extra_items)
        lines.append(f"### 📥 Live (email/calendario) ({len(extra_items)})")
        for it in extra_items:
            s = it.get("source", "extra")
            lines.append(f"- {s}{tag(s)}")
        lines.append("")

    # nota quarantena aggregata
    quar = [s for s, r in verdicts.items() if r.quarantined]
    if quar:
        lines.append(f"> ⚠️ {len(quar)} elemento/i in QUARANTENA (sospetta manipolazione): "
                     f"{', '.join(quar)}. L'assistente NON auto-processa il contenuto; rivedilo a mano.")
        lines.append("")

    if not any_news:
        lines.append("_Nessuna novita' dall'ultimo giro._")

    if save:
        save_state(root, snap)

    return "\n".join(lines).rstrip() + "\n"


def old_text(root: Path, source: str, key: str) -> str:
    """Recupera il testo di un item sparito, dallo stato salvato (per mostrarlo nel 'chiusi')."""
    st = load_state(root).get(source, {})
    v = st.get(key, {})
    return v.get("text", key)


# ============================================================
# CLI
# ============================================================
# POSTA: digest di Apple Mail, sola lettura (mail/daily.py)
# ============================================================
def _live_json() -> Path:
    """Il file che daily.py produce. Sta fuori dal git (posta personale/bancaria)."""
    return mail_daily.OUTDIR / "live.json"


def _mail_age_hours(f: Path, now: datetime) -> float:
    """Eta' del digest in ore. Se non esiste -> infinito, cioe': va rifatto."""
    if not f.exists():
        return float("inf")
    return (now - datetime.fromtimestamp(f.stat().st_mtime)).total_seconds() / 3600.0


def refresh_mail(root: Path, force: bool = False, now: datetime | None = None) -> tuple[str, str]:
    """Rifa il digest posta se manca o e' vecchio. Torna (esito, dettaglio) da stampare.

    Sola lettura per costruzione: daily.py legge Apple Mail e scrive due file. Non invia,
    non risponde, non marca come letto, non sposta (CLAUDE §5).
    Non alza MAI: se Mail non risponde si tiene il digest vecchio. Un briefing con posta
    stantia e' meglio di nessun briefing.
    Modulo posta spento in brain.json: non chiama Mail e torna ("spento", ...).
    """
    if not mail_daily.ENABLED:
        return "spento", "modulo non configurato: oggetto `mail` in .claude/config/brain.json"
    now = now or datetime.now()
    eta = _mail_age_hours(_live_json(), now)
    if not force and eta <= MAIL_MAX_AGE_H:
        return "riuso", f"digest di {eta:.1f}h fa"
    try:
        esito = mail_daily.run(giorni=1, timeout=MAIL_TIMEOUT_S)
    except Exception as e:
        vecchio = "digest precedente" if _live_json().exists() else "nessun digest"
        return "errore", f"{type(e).__name__}: {str(e)[:100]} ({vecchio})"
    return "aggiornato", f"{esito['totali']} email lette"


def load_mail(root: Path) -> list[dict]:
    """Legge il digest -> [{source, content}] per il guard.

    Il contenuto e' ESTERNO = DATI NON FIDATI (CLAUDE §5): qui non viene interpretato,
    passa da guard_batch() come ogni altra fonte esterna.
    Modulo posta spento: lista vuota (un digest rimasto su disco non si riusa).
    """
    if not mail_daily.ENABLED:
        return []
    f = _live_json()
    if not f.exists():
        return []
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return []
    return [d for d in data if isinstance(d, dict) and d.get("content")]


# ============================================================
def main() -> None:
    ap = argparse.ArgumentParser(description="Heartbeat advisor: briefing delle novita' (delta + guard).")
    ap.add_argument("--preview", action="store_true", help="stampa senza salvare lo stato (dry-run)")
    ap.add_argument("--reset", action="store_true", help="azzera lo stato e esci")
    ap.add_argument("--no-guard", action="store_true", help="salta il buttafuori LLM (solo diffing)")
    ap.add_argument("--no-route", action="store_true", help="non smistare le call in automatico (solo briefing)")
    ap.add_argument("--no-fetch", action="store_true", help="non scaricare le call da Granola (solo smistamento + briefing)")
    ap.add_argument("--extra", default=None, help="file JSON [{source,content}] da email/calendario in sessione")
    ap.add_argument("--no-mail", action="store_true", help="salta il giro posta automatico")
    ap.add_argument("--mail-fresh", action="store_true", help="rifa' il digest posta anche se recente")
    args = ap.parse_args()

    root = vault_root()
    if args.reset:
        p = state_path(root)
        if p.exists():
            p.unlink()
        print("stato heartbeat azzerato.")
        return

    # Fonti live. Un --extra esplicito VINCE (calendario, o un file fatto a mano); altrimenti
    # la posta del Mac entra da sola (vedi il blocco EMAIL in cima al file per il perche').
    extra = None
    if args.extra:
        extra = json.loads(Path(args.extra).read_text(encoding="utf-8"))
    elif not args.no_mail:
        esito, dett = refresh_mail(root, force=args.mail_fresh)
        extra = load_mail(root)
        if esito == "spento":
            print(f"posta: {dett}")
        else:
            print(f"posta: {esito} ({dett}), {len(extra)} non lette nel briefing")

    # scarica → smista → briefing. Lo scarico da Granola passa dall'API ufficiale
    # (fetch_granola.py). Non alza eccezioni: senza chiave o con la rete giù, il briefing
    # gira lo stesso.
    if not args.no_fetch:
        fetched = fg.sync_for_heartbeat(root, dry_run=args.preview)
        if fetched and fetched["written"]:
            print(fg.render_report(fetched, dry_run=args.preview))

    # rileva → smista: auto-smistamento delle call PRIMA del briefing (in preview = dry-run).
    # Le call smistate escono dall'inbox, così il briefing sotto elenca solo le ambigue rimaste.
    if not args.no_route:
        routed = rc.route(root, dry_run=args.preview)
        if routed["routed"] or routed["skipped"]:
            print(rc.render(routed, dry_run=args.preview))

    # Salute del vault PRIMA del briefing: se il push e' rotto o una call e' ferma da giorni,
    # e' la cosa piu' urgente sullo schermo, non una nota a pie' di pagina. Solo allarmi: quando
    # e' tutto a posto non si stampa nulla (anti-nagging, come il resto del motore).
    referto = hc.render(hc.esegui(root), solo_allarmi=True)
    if referto:
        print(referto + "\n")

    print(run_heartbeat(root, save=not args.preview, use_guard=not args.no_guard, extra_items=extra))


if __name__ == "__main__":
    main()
