# 2nd Brain Hero Mode · Copyright (c) 2026 Alessandro Pacifico (Pacibrand).
# Vedi LICENZA.md nella radice del vault.
"""
health_check.py: il controllo degli invarianti del vault. Deterministico, zero token.

PERCHE' ESISTE. I guasti che costano di piu' in un vault automatizzato sono quelli che non si
fanno notare:

  - il push su GitHub rotto da giorni, con la convinzione opposta (il vault "e' su GitHub");
  - il backup orario che fallisce a ogni giro, e l'unica traccia in un log che nessuno legge;
  - il contesto di sessione troncato: le daily recenti che spariscono INTERE, in silenzio;
  - lo smistamento delle call che non conosce un progetto, quindi certe call restano in inbox
    per sempre.

Il filo comune non e' la complessita': e' che ognuno **sembra acceso e non lo e'**. Un vault
che si controlla da solo costa una manciata di millisecondi; scoprirlo per caso costa settimane
di dati non salvati. Questo file esiste per rendere impossibile la seconda cosa.

COSA NON FA. Non ripara, non scrive nel vault, non tocca la rete. Guarda e riferisce: la
riparazione resta una decisione, non un effetto collaterale di un controllo.

MODULI SPENTI. Un controllo che riguarda un modulo non attivo (nessun repository git, nessun
remote, giro orario non installato, posta non configurata) non suona: dice in una riga che
non si applica.

Uso:
    python3 health_check.py            # stampa il referto
    python3 health_check.py --solo-allarmi
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from shared import read_text, vault_root  # noqa: E402

# --- soglie: oltre queste, e' un allarme ---
MAX_COMMIT_NON_PUSHATI = 3      # qualche commit in volo e' normale; una pila no
MAX_ORE_SENZA_BACKUP = 36       # un giorno e mezzo senza salvare = qualcosa non gira
MAX_ORE_SENZA_GIRO = 26         # il giro e' orario, ma di notte il Mac dorme: oltre un giorno e' fermo
MAX_ORE_SENZA_POSTA = 36        # il giro posta e' quotidiano: un giorno saltato (Mac spento) e' tollerato
MAX_GIORNI_CALL_IN_INBOX = 3    # una call ambigua si smista a mano, ma non in una settimana

# Etichetta launchd del giro orario (vedi AUTOMAZIONI.md e com.secondbrain.autopilot.plist).
LAUNCHD_AUTOPILOT = "com.secondbrain.autopilot"

OK, ALLARME = "OK", "ALLARME"


def _git(root: Path, *args: str) -> str:
    """git silenzioso: se fallisce torna stringa vuota invece di alzare."""
    try:
        r = subprocess.run(["git", "-C", str(root), *args],
                           capture_output=True, text=True, timeout=20)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def _is_repo(root: Path) -> bool:
    """Il vault e' un repository git? Si guarda la cartella, senza lanciare git: su un Mac senza
    gli strumenti da riga di comando `git` apre la finestra che propone di installarli."""
    return (root / ".git").exists()


def _has_remote(root: Path) -> bool:
    return bool(_git(root, "remote", "get-url", "origin"))


def _config(root: Path) -> dict:
    """La configurazione del vault (`.claude/config/brain.json`), o vuota se il lettore manca."""
    try:
        import brain_config
        return brain_config.load(root)
    except Exception:
        return {}


def _git_author(root: Path) -> str:
    """Chi firma i commit di questo computer: `git_author` di brain.json, altrimenti il nome
    configurato in git (`git config user.name`)."""
    autore = str(_config(root).get("git_author") or "").strip()
    return autore or _git(root, "config", "user.name")


# ============================================================
# I controlli. Ognuno torna (stato, titolo, dettaglio).
# ============================================================
def check_push(root: Path) -> tuple[str, str, str]:
    """I commit locali sono arrivati su GitHub? E' il guasto che costa di piu'."""
    if not _is_repo(root):
        return OK, "push", "non applicabile: il vault non e' un repository git"
    if not _has_remote(root):
        return OK, "push", "nessun remote: il vault e' salvato solo su questo computer"
    n = _git(root, "rev-list", "--count", "origin/main..main")
    if not n:
        return ALLARME, "push", ("non riesco a confrontare con origin/main (primo push mai fatto, "
                                 "ramo diverso da main, o remote irraggiungibile?)")
    n = int(n)
    if n > MAX_COMMIT_NON_PUSHATI:
        return ALLARME, "push", f"{n} commit NON su GitHub: il vault non e' salvato fuori dal computer"
    return OK, "push", "allineato con origin" if n == 0 else f"{n} commit in volo"


def check_backup(root: Path) -> tuple[str, str, str]:
    """Da quanto QUESTO COMPUTER non salva? Se il backup e' morto, questo e' il sintomo.

    Non basta guardare l'ultimo commit qualunque: nel clone di una routine cloud l'ultimo commit
    e' quello della routine stessa, quindi il controllo resterebbe verde anche col computer fermo
    da giorni. Per questo si filtra per AUTORE: i commit del computer (backup + sessioni) portano
    il nome dell'utente; la routine cloud firma diversamente. Nota: auto-backup.sh non committa
    quando il vault e' pulito, quindi un computer acceso ma inattivo puo' comunque superare la
    soglia. E' voluto: "registro fermo" va visto, il referto dice da quanto.
    """
    if not _is_repo(root):
        return OK, "backup", "non applicabile: il vault non e' un repository git"
    if not _git(root, "rev-parse", "--verify", "HEAD"):
        return OK, "backup", "nessun salvataggio ancora (repository appena creato)"
    autore = _git_author(root)
    filtro = [f"--author={autore}"] if autore else []
    ts = _git(root, "log", "-1", "--format=%ct", *filtro)
    if not ts:
        return ALLARME, "backup", (f"nessun commit di «{autore}» trovato: controlla `git_author` "
                                   "in .claude/config/brain.json")
    ore = (datetime.now() - datetime.fromtimestamp(int(ts))).total_seconds() / 3600
    if ore > MAX_ORE_SENZA_BACKUP:
        return ALLARME, "backup", f"ultimo salvataggio dal computer {ore:.0f}h fa: backup o computer fermi?"
    return OK, "backup", f"ultimo salvataggio dal computer {ore:.1f}h fa"


def check_giro_orario(root: Path) -> tuple[str, str, str]:
    """Il giro orario del Mac (autopilot: call + smistamento + posta + backup) sta girando?

    `check_backup` da solo non basta: il backup parte anche dall'hook di fine sessione, quindi
    resta verde mentre il giro orario e' morto e le call non entrano piu' nel vault. La causa
    tipica sta fuori dal vault (un aggiornamento che toglie l'interprete indicato nel plist),
    quindi qui si guarda il sintomo: da quanto il giro non scrive nel suo log.
    Il log e' locale al Mac (fuori da git): dove non esiste (giro mai installato, sessione
    cloud) il controllo non si applica.
    """
    log = root / ".claude" / "data" / "autopilot.log"
    if not log.exists():
        return OK, "giro orario", "non attivo qui (si installa a richiesta, solo su Mac: vedi AUTOMAZIONI.md)"
    date = re.findall(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\]", read_text(log), re.M)
    if not date:
        return ALLARME, "giro orario", "autopilot.log senza nessun giro registrato"
    ore = (datetime.now() - datetime.strptime(date[-1], "%Y-%m-%d %H:%M")).total_seconds() / 3600
    if ore <= MAX_ORE_SENZA_GIRO:
        return OK, "giro orario", f"ultimo giro {ore:.1f}h fa"
    causa = ""
    try:                                         # indizio sulla causa: l'interprete del plist esiste ancora?
        import plistlib
        plist = Path.home() / "Library" / "LaunchAgents" / f"{LAUNCHD_AUTOPILOT}.plist"
        with open(plist, "rb") as f:
            programma = plistlib.load(f).get("ProgramArguments", [""])[0]
        if programma and not Path(programma).exists():
            causa = f" L'interprete del plist non esiste più: `{programma}`."
    except Exception:
        pass
    return (ALLARME, "giro orario",
            f"fermo da {ore:.0f}h (ultimo giro {date[-1]}): call, smistamento e backup orario "
            f"non girano.{causa}")


def check_giro_posta(root: Path) -> tuple[str, str, str]:
    """Il giro posta quotidiano (mail/loop_sync.py, dentro autopilot) riesce?

    E' il giro che aggiorna i loop dalle email senza che l'utente guardi: se si ferma, i dossier
    invecchiano in silenzio, che e' proprio il guaio che doveva togliere.
    Stato locale al Mac (fuori da git): dove non esiste (posta non configurata, sessione cloud)
    il controllo non si applica.
    """
    f = root / ".claude" / "data" / "mail-sync" / "state.json"
    if not f.exists():
        return OK, "giro posta", "non attivo qui (posta non configurata, o giro mai partito)"
    import json
    try:
        state = json.loads(read_text(f))
    except ValueError:
        return ALLARME, "giro posta", "state.json illeggibile"
    ultimo_ok = state.get("ultimo_ok")
    ore = ((datetime.now() - datetime.fromisoformat(ultimo_ok)).total_seconds() / 3600
           if ultimo_ok else None)
    if ore is not None and ore <= MAX_ORE_SENZA_POSTA:
        return OK, "giro posta", f"ultimo riuscito {ore:.0f}h fa"
    causa = f" Ultimo errore: {state['errore']}" if state.get("esito") == "errore" else ""
    quando = f"da {ore:.0f}h" if ore is not None else "mai riuscito"
    return ALLARME, "giro posta", f"{quando}: i loop non si aggiornano dalla posta.{causa}"


def check_inbox(root: Path) -> tuple[str, str, str]:
    """Invariante: una call fuori dall'inbox e' gia' al suo posto; una in inbox aspetta te."""
    d = root / "00-inbox" / "calls"
    if not d.exists():
        return OK, "inbox call", "nessuna inbox"
    ferme = []
    limite = datetime.now() - timedelta(days=MAX_GIORNI_CALL_IN_INBOX)
    for f in d.glob("20*.md"):
        # La data si legge dal NOME del file, non dal filesystem: in un clone fresco (routine
        # cloud) il mtime e' l'ora del checkout, quindi il controllo non si accenderebbe mai.
        # I nomi delle call iniziano sempre con AAAA-MM-GG.
        m = re.match(r"(\d{4}-\d{2}-\d{2})", f.name)
        try:
            quando = datetime.strptime(m.group(1), "%Y-%m-%d") if m \
                else datetime.fromtimestamp(f.stat().st_mtime)
        except ValueError:
            quando = datetime.fromtimestamp(f.stat().st_mtime)
        if quando < limite:
            ferme.append(f.name)
    if ferme:
        return ALLARME, "inbox call", f"{len(ferme)} call ferme da >{MAX_GIORNI_CALL_IN_INBOX}g: {ferme[0][:44]}…"
    return OK, "inbox call", "vuota o tutto recente"


def _rotte_note(root: Path) -> tuple[set[str], set[str]]:
    """(id dei progetti, cartelle di destinazione) che lo smistamento conosce.

    La mappa vive in `.claude/config/brain.json` (letta da `brain_config.routing`). Per
    compatibilita' si raccolgono anche gli id eventualmente scritti dentro route_calls.py."""
    ids: set[str] = set()
    dests: set[str] = set()
    try:
        import brain_config
        for r in brain_config.routing(root):
            ids.add(str(r.get("project", "")))
            dests.add("/".join(r.get("dest") or ()))
    except Exception:
        pass
    testo = read_text(root / ".claude" / "scripts" / "route_calls.py")
    ids |= set(re.findall(r'"project":\s*"([^"]+)"', testo))
    return ids, dests


def check_router(root: Path) -> tuple[str, str, str]:
    """Ogni progetto che RICEVE call e' nella mappa dello smistamento?

    Un progetto con delle call ma fuori dalla mappa non viene mai riconosciuto: le sue call
    restano in inbox per sempre. Un progetto nuovo reintroduce il buco senza che nessuno se ne
    accorga, a meno che qualcuno controlli.
    """
    if not (root / ".claude" / "scripts" / "route_calls.py").exists():
        return OK, "router", "smistamento call non installato (route_calls.py assente)"
    ids, dests = _rotte_note(root)
    mancanti = []
    for calls_dir in root.glob("10-lavoro/**/knowledge/calls"):
        if not any(calls_dir.glob("20*.md")):
            continue
        nome = calls_dir.parent.parent.name
        rel = calls_dir.relative_to(root).as_posix()
        if nome not in ids and rel not in dests:
            mancanti.append(nome)
    if mancanti:
        return ALLARME, "router", ("progetti con call ma FUORI dalla mappa (aggiungili a "
                                   f".claude/config/brain.json): {', '.join(mancanti)}")
    return OK, "router", f"{len(ids)} progetti mappati, nessuno scoperto"


def check_contesto(root: Path) -> tuple[str, str, str]:
    """Le fonti di inizio sessione stanno sotto il tetto, o si perde la coda in silenzio?"""
    hook = root / ".claude" / "hooks" / "session-start-context.py"
    testo = read_text(hook)
    m = re.search(r"^MAX_CONTEXT_CHARS\s*=\s*([\d_]+)", testo, re.M)
    if not m:
        return OK, "contesto", "tetto non trovato (hook assente o cambiato)"
    tetto = int(m.group(1).replace("_", ""))
    fonti = sum(len(read_text(root / p)) for p in
                ("CAPISALDI.md", "ARCHITETTURA.md", "02-memoria/me.md", "02-memoria/SOUL.md"))
    fonti += 4500   # testata + daily recenti, stimate
    if fonti > tetto:
        return ALLARME, "contesto", f"fonti ~{fonti:,} > tetto {tetto:,}: la CODA viene tagliata"
    return OK, "contesto", f"~{fonti:,} su {tetto:,} ({100*fonti//tetto}% del tetto)"


# Budget per file delle fonti caricate a ogni sessione. La somma (42.000) piu' testata e daily
# (~4.500) sta sotto MAX_CONTEXT_CHARS dell'hook (58.000): se ogni file rispetta il suo, il tetto
# totale non si puo' sfondare. Oltre il budget si compatta (il dettaglio va nelle pagine `me-*`
# del wiki, nel file resta una riga), non si alza il numero.
BUDGET_FILE = {
    "CAPISALDI.md": 14_000,
    "ARCHITETTURA.md": 9_000,
    "02-memoria/me.md": 12_000,
    "02-memoria/SOUL.md": 7_000,
}
SOGLIA_BUDGET = 0.8  # si avvisa all'80%: resta spazio per compattare con calma, prima del taglio


def check_budget_file(root: Path) -> tuple[str, str, str]:
    """Ogni fonte di inizio sessione sta nel suo budget? Il tetto totale avvisa troppo tardi.

    Il controllo sul totale suona solo a tetto sfondato, cioe' a coda del contesto gia' tagliata.
    Intanto un file come me.md puo' crescere fino a meta' del tetto, perche' ogni lezione promossa
    lo allunga e niente lo accorcia. Il budget per file dice QUALE file cresce, e lo dice all'80%,
    quando c'e' ancora spazio per compattarlo.
    """
    oltre = []
    for rel, budget in BUDGET_FILE.items():
        n = len(read_text(root / rel))
        if n > budget * SOGLIA_BUDGET:
            oltre.append(f"{rel} {n:,}/{budget:,} ({100*n//budget}%)")
    if oltre:
        return ALLARME, "budget file", "da compattare: " + " · ".join(oltre)
    return OK, "budget file", "ogni fonte di sessione sotto l'80% del suo budget"


def check_essenziali_progetti(root: Path) -> tuple[str, str, str]:
    """Il contesto di ogni progetto sta nel suo tetto?

    `project-context.py` carica da solo metodo ed essenziali (`references/`) quando si nomina un
    progetto, entro un tetto. Un file che cresce oltre non si perde (resta su disco e si apre a
    richiesta) ma smette di entrare da solo: va compattato PRIMA, con la stessa regola di me.md
    (il dettaglio scende nel wiki del progetto, nell'essenziale resta la riga). Si avvisa all'80%.
    """
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "project_context", root / ".claude" / "hooks" / "project-context.py")
        pc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(pc)
        mappa = pc.progetti()
    except Exception:
        return OK, "essenziali progetti", "non applicabile: hook del contesto di progetto assente"
    if not mappa:
        return OK, "essenziali progetti", "non applicabile: nessun progetto in brain.json"
    oltre = []
    for pid, (cartella, _) in mappa.items():
        ref = root / cartella / "references"
        if not ref.is_dir():
            continue
        metodo = len(read_text(ref / "metodo.md"))
        altri = sum(len(read_text(p)) for p in ref.glob("*.md")
                    if p.name not in ("metodo.md", "_README.md"))
        if metodo > pc.MAX_METODO * SOGLIA_BUDGET:
            oltre.append(f"{pid} metodo {metodo:,}/{pc.MAX_METODO:,}")
        if altri > pc.MAX_REFERENCES * SOGLIA_BUDGET:
            oltre.append(f"{pid} essenziali {altri:,}/{pc.MAX_REFERENCES:,}")
    if oltre:
        return ALLARME, "essenziali progetti", "da compattare: " + " · ".join(oltre)
    return OK, "essenziali progetti", "metodo ed essenziali di ogni progetto sotto l'80% del tetto"


def check_coda_promote(root: Path) -> tuple[str, str, str]:
    """Distingue le due popolazioni della coda: lavorabile vs bloccata sull'utente.

    Un contatore solo su due popolazioni fa sembrare la coda sempre rotta: gli hold non se ne
    vanno per definizione (contraddizioni, dati personali, progetti inesistenti), quindi gonfiano
    il numero per sempre. Qui si contano separati.
    """
    testo = read_text(root / "02-memoria" / "PROMOTE-QUEUE.md")
    if not testo or "## In attesa" not in testo:
        return OK, "coda memoria", "coda assente o vuota"
    attesa = testo.split("## In attesa", 1)[1].split("\n## ", 1)[0]
    voci = [r for d, r in re.findall(r"^### \[(\d{4}-\d{2}-\d{2})\](.*)$", attesa, re.M)
            if not d.startswith("AAAA")]
    hold = [r for r in voci if "HOLD" in r or "🔵" in r or "CONTRADDIZIONE" in r.upper()]
    lavorabili = len(voci) - len(hold)
    if lavorabili > 15:
        return ALLARME, "coda memoria", f"{lavorabili} drenabili (+{len(hold)} bloccati su di te): `/promote-triage`"
    return OK, "coda memoria", f"{lavorabili} drenabili, {len(hold)} bloccati su di te"


CONTROLLI = [check_push, check_backup, check_giro_orario, check_giro_posta, check_inbox, check_router, check_contesto,
             check_budget_file, check_essenziali_progetti, check_coda_promote]


def esegui(root: Path) -> list[tuple[str, str, str]]:
    esiti = []
    for c in CONTROLLI:
        try:
            esiti.append(c(root))
        except Exception as e:                                  # un controllo rotto non ferma gli altri
            esiti.append((ALLARME, c.__name__, f"controllo fallito: {type(e).__name__}"))
    return esiti


def render(esiti: list[tuple[str, str, str]], solo_allarmi: bool = False) -> str:
    allarmi = [e for e in esiti if e[0] == ALLARME]
    if solo_allarmi and not allarmi:
        return ""
    righe = []
    if allarmi:
        righe.append(f"### 🩺 Salute del vault: {len(allarmi)} da guardare")
    elif not solo_allarmi:
        righe.append("### 🩺 Salute del vault: tutto a posto")
    for stato, titolo, dettaglio in esiti:
        if solo_allarmi and stato == OK:
            continue
        righe.append(f"- {'⚠️' if stato == ALLARME else '✅'} **{titolo}**: {dettaglio}")
    return "\n".join(righe)


def main() -> None:
    ap = argparse.ArgumentParser(description="Controllo invarianti del vault (sola lettura).")
    ap.add_argument("--solo-allarmi", action="store_true", help="stampa solo cio' che non va")
    args = ap.parse_args()
    out = render(esegui(vault_root()), solo_allarmi=args.solo_allarmi)
    if out:
        print(out)


if __name__ == "__main__":
    main()
