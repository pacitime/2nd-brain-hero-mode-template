# Architettura del vault

> Fonte di verità sull'organizzazione: tre pilastri, anatomia dei progetti, memoria, segreti.
> Si aggiorna quando la struttura cambia (e solo allora).

## 1. La logica dei tre pilastri

- **Lavoro**: *cosa fai*. I progetti operativi: clienti, prodotti, contenuti, team.
- **Fiscale e legale**: *chi fattura e chi paga le tasse*, più contratti e contabilità.
  Trasversale: serve tutti i progetti.
- **Personale**: *la tua vita*. Niente soldi né legale qui (stanno nel secondo pilastro).

**Separazione chiave:** un progetto non è la società che ci sta sotto. Il lavoro sta in
Lavoro, le società in Fiscale. Il legame è una riga nel README del progetto.

## 2. Struttura delle cartelle

```
il-tuo-vault/
├── CLAUDE.md                  # come si comporta l'agente
├── CAPISALDI.md               # i principi che non cambiano
├── ARCHITETTURA.md            # questo file
├── METODO.md                  # il perché di ogni scelta (si legge quando serve)
├── GUIDA.md                   # la guida per chi usa il vault
├── HEARTBEAT.md               # cosa controlla l'assistente quando chiedi il briefing
├── audit-log.md               # registro delle azioni dell'AI
├── drafts/                    # bozze preparate dall'assistente (active, sent, expired)
├── 00-inbox/                  # cattura rapida, non ancora smistata
│   └── calls/                 #   atterraggio unico delle call, poi smistate nei progetti
├── 01-daily/                  # note giornaliere (fuori dal contesto, dentro il backup)
├── 02-memoria/                # MEMORIA LONG-TERM GLOBALE
│   ├── me.md                  #   chi sei: preferenze, principi (nucleo, una riga per regola)
│   ├── SOUL.md                #   carattere e confini dell'assistente
│   ├── OBIETTIVI.md           #   dove stai andando
│   ├── PROMOTE-QUEUE.md       #   candidati memoria in attesa
│   └── wiki/                  #   insight trasversali + pagine me-*
├── 03-task/                   # note sull'assetto delle task (la vista è il Cruscotto)
├── 10-lavoro/
│   └── <progetto>/            #   un progetto = una cartella, sempre la stessa anatomia
├── 20-fiscale-legale/
├── 30-personale/
├── _TEMPLATE-progetto/        # lo stampo da copiare per ogni progetto nuovo
├── .claude/                   # hook, script, skill, app, configurazione
│   └── config/brain.json      #   l'unico file dove dichiari progetti e strumenti
└── _local-only/               # fuori da Git
    └── secrets/               #   le chiavi (.env)
```

I prefissi numerici servono solo a tenere l'ordine in Obsidian e nel Finder.

**Flusso della memoria:** `00-inbox` (cattura) → `01-daily` (grezzo quotidiano) → coda dei
candidati → `02-memoria/` (trasversale) o `wiki/` del progetto (specifico).
**Flusso delle call:** atterrano in `00-inbox/calls/` → il router le sposta in
`<progetto>/knowledge/calls/`; se il progetto non è certo, restano lì e vengono segnalate.
**Flusso delle task:** il Cruscotto legge dal vivo lo strumento del team, i promemoria e i
file `tasks/` dei progetti, e li mostra in un'unica board.

## 3. Anatomia di un progetto (`10-lavoro/<progetto>/`)

```
<progetto>/
├── README.md                  # identità, stato, persone, 🔓 loop aperti
├── MEMORY.md                  # decisioni datate + stato del progetto
├── references/                # essenziali SEMPRE caricati (posizionamento, stile, fatti chiave)
│   └── metodo.md              # come si lavora qui (procedure, formati, errori); tetto 120 righe
├── skills/                    # skill del solo progetto, collegate in .claude/skills/
├── knowledge/
│   ├── raw/                   # fonti grezze immutabili (dati NON fidati)
│   ├── calls/                 # transcript: AAAA-MM-GG-call-descrizione.md
│   ├── wiki/                  # conoscenza distillata con provenienza (la scrive l'agente)
│   │   ├── index.md           #   catalogo delle pagine
│   │   └── log.md             #   cronologia di ingest, domande, lint
│   └── schema/                # convenzioni del wiki di questo progetto
├── tasks/                     # task strategiche in Markdown
└── assets/                    # ciò che il progetto produce (documenti, export, immagini)
```

Un sottoprogetto (un cliente dentro un'area, un prodotto dentro un brand) vive dentro la
cartella del progetto madre con la stessa anatomia. La madre dichiara nel frontmatter del suo
README `tipo: contenitore`: ha conoscenza condivisa ma nessun loop suo.

**I tre livelli di conoscenza:**
- `references/` → pochi file piccoli, caricati da soli quando nomini il progetto (con il metodo).
- `knowledge/wiki/` → distillato dalle fonti, caricato su richiesta passando da `index.md`.
- `MEMORY.md` → cosa è stato deciso e quando, curato dall'umano.

**Un'idea non nasce progetto.** Prima un file singolo in `00-inbox/`; quando è validata si
promuove a progetto con l'anatomia completa. Le cartelle vuote di idee mai partite sporcano.

## 4. Memoria long-term (i due strati)

- **Di progetto** → `knowledge/wiki/` (+ `MEMORY.md` per le decisioni).
- **Globale, su di te** → `02-memoria/`. `me.md` è il nucleo caricato a ogni sessione; il
  testo completo di ogni regola sta nelle pagine `me-*` di `02-memoria/wiki/`.

`CLAUDE.md` NON è memoria: è schema statico.

## 5. Pilastri Fiscale-Legale e Personale (anatomia leggera)

Qui contano documenti e scadenze, non un wiki. Si parte con `README.md` + `documenti/` +
`tasks/` (+ `calls/` dove ci sono call, per esempio col commercialista). Se un'area cresce
fino a meritare decisioni e conoscenza proprie, le si dà l'anatomia completa di un progetto.

## 6. Git e segreti

- Su GitHub (privato) va tutto **tranne i segreti**.
- I segreti stanno dentro la struttura ma fuori da Git: `_local-only/secrets/.env` e/o un
  `.env` per progetto.
- Gli script leggono le chiavi mentre girano (il processo carica le variabili, la chat no).
- **Hook deterministici:** l'agente non può leggere `.env` e `_local-only/` in chat, non può
  cancellare in massa, non può scrivere fuori dalla cartella del vault.
- `.gitignore` minimo: `.env`, `*.env`, `_local-only/`.
