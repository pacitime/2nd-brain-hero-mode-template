# Cruscotto: la board delle tue task

Una piccola web-app che gira **solo sul tuo computer** e mette in un'unica board settimanale le
task di tre fonti:

- **le task del vault**: i file `<progetto>/tasks/*.md`, riletti a ogni aggiornamento;
- **ClickUp** (facoltativo): le task assegnate a te, lette dal vivo con la tua chiave;
- **Apple Promemoria** (facoltativo, solo Mac): una sola lista, quella che scegli tu.

Una fonte che non hai configurato si spegne da sola. Senza ClickUp e senza Promemoria restano
le task del vault e la board funziona uguale.

Il server ascolta solo su `127.0.0.1` (localhost): la board non è raggiungibile da altri
computer e i tuoi dati non escono dal tuo.

## Avvio a mano

Dalla cartella del vault:

```bash
python3 .claude/apps/cruscotto/server.py
```

Poi apri nel browser l'indirizzo che compare (di norma `http://127.0.0.1:8765`). Per fermarlo:
`Ctrl+C`. All'avvio il server dice in tre righe quali fonti sono accese:

```
Cruscotto web → http://127.0.0.1:8765   (Ctrl+C per fermare)
  ClickUp: ClickUp non configurato
  Promemoria: lista "Lavoro"
  Calendario: spento
```

Serve solo Python 3 (nessuna libreria da installare).

## Come si usa

- **Settimana / Per progetto**: due viste della stessa board. Sotto la settimana trovi le
  scadute, le task più avanti e il backlog (senza data).
- **Trascina una card** su un giorno per cambiarle la data; trascinala sul backlog per toglierla.
- **Spunta** la casella per completarla: la task si chiude sulla sua fonte (riga `- [x]` nel
  file, task chiusa su ClickUp, promemoria completato).
- **Clicca la card** per il dettaglio: titolo intero, tag, note, sottotask, origine.
- **＋ Aggiungi** crea una task nuova nel file `tasks/aperti.md` di un progetto, su Promemoria
  o in una lista ClickUp.
- **Filtri in alto**: uno per ogni progetto dichiarato e per ogni tag trovato nelle task.

### Il formato delle task nei file

È quello del plugin Tasks di Obsidian:

```
- [ ] Testo della task 📅 2030-06-30 ⏫ #progetto-esempio
    > Una nota: righe che iniziano con > subito sotto la task
    - [ ] Una sottotask: riga rientrata di 4 spazi
```

- **Il primo tag decide il progetto**, cioè filtro e colore. Una task senza tag prende il
  progetto della cartella in cui si trova.
- Priorità: 🔺 e ⏫ alta, 🔼 media, 🔽 e ⏬ bassa.
- Una task spuntata (`- [x]`) non compare più in board.

## Configurazione

Tutto ciò che è tuo sta in `.claude/config/brain.json`. **Dopo ogni modifica il cruscotto va
riavviato** (legge il file solo all'avvio).

| Campo | Cosa fa |
|---|---|
| `projects` | Ogni progetto diventa un filtro e una destinazione di "Aggiungi": le task nuove finiscono in `<path>/tasks/aperti.md`. |
| `reminders_list` | Nome della lista di Apple Promemoria da mostrare. Solo quella: le altre tue liste non entrano mai in board. |
| `calendars` | Nomi dei calendari da leggere, se accendi il calendario. Vuoto = tutti. |
| `cruscotto.port` | Porta locale. Cambiala se la 8765 è occupata. |
| `cruscotto.reminders` | `false` spegne Promemoria in board. |
| `cruscotto.reminders_store_fallback` | `true`: se Promemoria non risponde, i promemoria si leggono (in sola lettura) dall'archivio locale dell'app. Vedi "Permessi di macOS". |
| `cruscotto.calendar` | `true` mostra in board gli eventi dei prossimi 7 giorni di Apple Calendario. |
| `clickup.*` | Vedi sotto. |

### ClickUp

Due cose: la **chiave** e gli **id**.

La chiave non va mai in `brain.json`. Sta nel file `_local-only/secrets/.env`, in una riga:

```
CLICKUP_TOKEN=la-tua-chiave
```

Il cruscotto la legge solo da quel file (non da una variabile d'ambiente) e la usa solo per
parlare con ClickUp.

Gli id stanno in `brain.json`, tutti fra virgolette:

```json
"clickup": {
  "member_id": "",
  "workspaces": [
    {"id": "<id-workspace>", "tag": "team", "lists": []}
  ],
  "exclude_statuses": ["done", "complete", "closed"],
  "quick_add": {"Team · Generale": "<id-lista>"},
  "delegated_lists": ["<id-lista>"],
  "mention_scopes": [{"workspace": "<id-workspace>", "spaces": []}]
}
```

- `workspaces`: i workspace da cui leggere le task assegnate a te. **Vuoto = ClickUp spento,
  nessuna chiamata.** `tag` è l'etichetta data in board alle task che su ClickUp non hanno tag
  (decide filtro e colore). `lists`, se non è vuoto, tiene solo le task di quelle liste.
- `member_id`: il tuo id utente. Lascialo vuoto: il cruscotto lo chiede a ClickUp con la chiave.
- `exclude_statuses`: gli stati le cui task non vuoi vedere in board (aggiungi i tuoi, per
  esempio `"backlog"`).
- `quick_add`: le liste proposte da "＋ Aggiungi", nella forma `"Etichetta nel menu": "id lista"`.
- `delegated_lists`: accende il riquadro **Delegate**, cioè le task create da te e assegnate ad
  altri in quelle liste, con il loro stato. Sola lettura.
- `mention_scopes`: accende il riquadro **Menzioni**, cioè i commenti in cui qualcuno ti ha
  menzionato e a cui non hai ancora risposto (ultimi 30 giorni, aggiornati ogni 15 minuti).
  `spaces` vuoto = tutto il workspace. La prima scansione legge i commenti di ogni task: su un
  workspace grande conviene indicare gli spazi.

A piè di pagina la board dice sempre com'è messo ClickUp: "ClickUp non configurato", "manca la
chiave", "non raggiungibile" (con il motivo, per esempio una chiave rifiutata) oppure "connesso".

### Dove finiscono le cose che scrivi

- Su una **task del vault**, note e sottotask si scrivono **nel file markdown**: restano
  leggibili in Obsidian, vanno in git e nel backup.
- Su una task di **ClickUp** o di **Promemoria**, la nota resta **solo sul tuo computer**
  (`_local-only/cruscotto-note.json`) e non viene scritta sul servizio. Le sottotask da qui si
  aggiungono solo alle task del vault.
- Anche la priorità a pallini dei promemoria, le menzioni scartate e la cache delle menzioni
  sono file locali in `_local-only/`.

## Avvio automatico al login (Mac)

Il file `com.secondbrain.cruscotto.plist` di questa cartella è un **modello** per `launchd`, il
sistema di macOS che tiene accesi i programmi. Va riempito e copiato, non collegato.

```bash
cd /percorso/del/tuo/vault
sed -e "s|__VAULT__|$PWD|g" \
    -e "s|__PYTHON__|$(command -v python3)|g" \
    -e "s|__HOME__|$HOME|g" \
    .claude/apps/cruscotto/com.secondbrain.cruscotto.plist \
    > ~/Library/LaunchAgents/com.secondbrain.cruscotto.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.secondbrain.cruscotto.plist
```

Da quel momento il cruscotto parte al login e riparte da solo se si ferma. Il suo registro è
in `~/Library/Logs/secondbrain-cruscotto.log`.

- **Riavviarlo** (dopo una modifica a `brain.json`):
  `launchctl kickstart -k gui/$(id -u)/com.secondbrain.cruscotto`
- **Spegnerlo e toglierlo**: `launchctl bootout gui/$(id -u)/com.secondbrain.cruscotto`, poi
  cancella il file in `~/Library/LaunchAgents/`.
- Non tenerlo acceso due volte (a mano e con launchd): il secondo trova la porta occupata e
  si ferma dicendolo.

### Un'icona da doppio click (facoltativa)

`launch.applescript` accende il server se è spento e apre la board in una finestra senza barre
(Chrome o Brave; altrimenti il browser predefinito). Per farne un'app:

```bash
osacompile -o .claude/apps/cruscotto/Cruscotto.app .claude/apps/cruscotto/launch.applescript
```

Poi trascina `Cruscotto.app` nel Dock. L'app deve **restare in questa cartella**: è da lì che
capisce dov'è il vault. Non è inclusa già compilata perché un'app compilata si porta dentro i
percorsi del computer su cui è nata.

## Trappole di macOS

- **launchd ignora i collegamenti.** In `~/Library/LaunchAgents/` deve esserci una **copia
  vera** del plist, non un alias o un symlink: per sicurezza macOS non li carica. Quindi se
  cambi il modello qui nel vault, la copia installata **non** si aggiorna da sola: va rifatta
  (stesso comando `sed` di sopra, poi `bootout` e `bootstrap`).
- **Aggiornare Python con Homebrew vuol dire riavviare subito il cruscotto.** Il processo resta
  acceso con l'interprete vecchio, ma la sua cartella non c'è più: i moduli non ancora caricati
  falliscono (`No module named ...`) e macOS può negargli i file del vault (`Operation not
  permitted`). A schermo spariscono le task e resta solo ciò che era in memoria. Rimedio:
  `launchctl kickstart -k ...` come sopra. E nel plist usa un percorso di Python che un
  aggiornamento non cancella: quello che dà `command -v python3`, non un percorso con dentro il
  numero di versione completo.
- **Permessi (TCC).** macOS chiede il permesso la prima volta che un programma tocca i dati di
  un altro. Per il cruscotto:
  - *Automazione*: alla prima lettura di Promemoria (o di Calendario) compare la richiesta
    "python vuole controllare Promemoria". Va accettata. Se l'hai rifiutata: Impostazioni di
    Sistema > Privacy e sicurezza > Automazione.
  - *Cartelle protette*: se il vault sta in Scrivania, Documenti o Download, macOS può negare
    quei file a un processo avviato da launchd (`Operation not permitted`), anche se dal
    terminale tutto funziona. Due strade: tenere il vault fuori da quelle cartelle, oppure
    dare "Accesso completo al disco" all'interprete Python usato nel plist. Il permesso è
    legato a quell'interprete: dopo un aggiornamento di Python può andare ridato.
  - *Archivio di Promemoria*: il ripiego `reminders_store_fallback` legge una cartella di
    un'altra app. A un processo launchd macOS la nega finché l'interprete non ha "Accesso
    completo al disco"; e quando la nega, l'elenco dei file risulta semplicemente vuoto, senza
    errore. In alternativa una shell che ha accesso può copiare l'archivio in
    `_local-only/reminders-copy.sqlite`: il cruscotto legge anche quella copia, e sempre solo
    la tua lista.
- **Promemoria non trova la lista** (errore `-1728`): la lista scritta in `reminders_list` non
  esiste su questo Mac. O non l'hai ancora creata con quel nome esatto, o esiste sull'iPhone ma
  l'account iCloud di questo Mac non la sincronizza. Per vederlo da soli:
  `osascript .claude/scripts/reminders/pull.applescript "Lavoro"`. Non è un guasto del cruscotto.

## Com'è fatto, e perché

Per chi ci mette le mani. Sono le lezioni che hanno dato forma al codice.

- **Lettura dal vivo, cache in memoria, ripiego su disco.** Una fonte lenta (osascript, API)
  non sta mai sul percorso di `/api/tasks`: ha il suo giro in un thread di background, e la
  richiesta serve la cache all'istante. Una lettura bloccante dentro la richiesta rende la
  board inutilizzabile (Promemoria a freddo può metterci decine di secondi).
- **Una cache che non dice di essere vecchia mente.** Se il giro di una fonte fallisce si tiene
  l'ultima fotografia buona, ma l'errore si registra e la board lo mostra: `/api/tasks`
  restituisce `reminders: {ok, err, since, mode}` e il frontend accende il banner "Promemoria
  non raggiungibile" con l'ora dell'ultimo dato vero. Vale anche per il guasto muto: un giro
  fermo da più di cinque minuti senza aver segnalato errori accende lo stesso banner. E un
  giro che solleva un'eccezione non deve uccidere il thread: si registra e si riprova.
- **Prima di riavviare, dire cosa sparirà.** Un riavvio butta la cache: per chi guarda la board,
  dati vecchi ma visibili diventano una lista vuota. Prima il ripiego e l'avviso, poi il riavvio.
- **La modale si aggancia a una chiave stabile, non a un indice.** Gli identificativi interni
  delle card si riassegnano a ogni aggiornamento (ogni 90 secondi): la modale aperta ritrova la
  sua task con la chiave `file|riga|id ClickUp|testo`, altrimenti dopo un refresh mostrerebbe
  la task sbagliata. Stessa famiglia: il testo che stai scrivendo in una nota viene fotografato
  e rimesso al suo posto, con cursore e selezione, a ogni ridisegno; chiudere con note non
  salvate chiede conferma; un trascinamento non apre il dettaglio.
- **Mai fidarsi del numero di riga.** Prima di scrivere in un file task il server controlla che
  quella riga sia ancora quella task (confronto sul testo pulito). Se il file è cambiato nel
  frattempo, rifiuta e chiede di ricaricare. Le scritture sono una alla volta, e sono ammessi
  solo file `.md` dentro una cartella `tasks/` del vault.
- **Una nota è della task solo se le sta attaccata.** Le righe `> ...` contano come nota solo
  se seguono subito la task: un blockquote qualunque nel file non viene scambiato per la nota
  di una task a caso.
- **Sottotask ClickUp sotto la madre.** L'API le restituisce in lista piatta col campo
  `parent`: il server le rimette sotto la madre (se è in lista anche lei), una sottotask di
  sottotask sale alla madre di primo livello, l'ordine è quello di creazione. Le sottotask già
  chiuse si chiedono a parte, una lettura per ogni madre che ha figlie: senza, la barra di
  avanzamento tornerebbe indietro a ogni spunta (da 1/4 a 0/3).
- **Il cruscotto non scrive sui servizi esterni più di quanto gli chiedi.** Completare e
  spostare una task sono azioni tue, esplicite. Note e priorità locali restano locali. Togliere
  la scadenza a un promemoria da qui non si può (AppleScript non lo permette): la board lo dice
  invece di fallire in silenzio.
- **Niente elenchi cablati nella pagina.** Filtri, colori e menu delle destinazioni si
  costruiscono dalla risposta di `/api/tasks` (`projects`, `targets`, tag presenti nelle task).
  Il colore di un progetto dichiarato dipende dalla sua posizione in `brain.json`; quello di
  ogni altro tag da un hash del nome, quindi resta sempre lo stesso.

## Test

Nessuno tocca il vault vero, ClickUp o Apple: lavorano su una cartella temporanea con le
letture sostituite.

```bash
python3 .claude/apps/cruscotto/test_config.py             # 37 controlli: configurazione vuota, compilata, scritta male
python3 .claude/apps/cruscotto/test_clickup_subtasks.py   # 14 controlli: sottotask ClickUp sotto la madre
python3 .claude/apps/cruscotto/test_note_subtask.py       # 35 controlli: note e sottotask nel markdown, difese
python3 .claude/apps/cruscotto/test_reminders_loop.py     # 7 controlli: il giro dei promemoria non muore e non mente
```

## Solo Mac?

Board, task del vault e ClickUp funzionano ovunque giri Python 3. Promemoria, Calendario,
notifiche delle menzioni, avvio al login e icona nel Dock sono solo per macOS: su un altro
sistema quei pezzi restano spenti da soli.
