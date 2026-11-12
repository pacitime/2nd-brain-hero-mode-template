---
tipo: nota-struttura
---

# 03-task: come sono organizzate le task

> **La vista unica è l'app Cruscotto** (`.claude/apps/cruscotto/`): una board che si apre nel
> browser, solo su questo computer (`http://127.0.0.1:8765`; la porta è `cruscotto.port` in
> `.claude/config/brain.json`). Questa cartella non contiene le tue task: contiene questa nota e,
> se li usi, i mirror descritti sotto.

## Da dove arrivano le task

Il Cruscotto legge **dal vivo**, a ogni aggiornamento:
- **Task native del vault** → i file `<progetto>/tasks/*.md`. Funzionano sempre, senza
  configurare nulla.
- **ClickUp** (se lo usi) → le task assegnate a te nei workspace elencati in `brain.json`. Serve
  la chiave `CLICKUP_TOKEN` in `_local-only/secrets/.env`.
- **Apple Promemoria** (solo Mac, se lo usi) → una sola lista, quella indicata in
  `reminders_list`. Le altre liste restano fuori.

Una fonte non configurata si spegne da sola: con le sole task native la board funziona uguale.

## Cosa può comparire in questa cartella

- `clickup-mirror/`: una **fotografia** su file delle task ClickUp. La scrive Claude quando gli
  chiedi `/task-sync pull` e, se hai attivato la routine notturna in cloud, la routine ogni
  notte (task assegnate a te e task delegate al team, con il loro stato). Serve al briefing
  (`/heartbeat`) per dirti cosa è cambiato, e al Cruscotto quando manca la chiave ClickUp.
- `reminders-mirror/`: la stessa cosa per i promemoria. Facoltativa: serve solo al briefing.

Regole dei mirror:
- **Non sono la fonte di verità.** La fonte è ClickUp (o Promemoria): un mirror può essere
  vecchio, e si rigenera.
- **Chi li scrive legge soltanto.** Né `/task-sync pull` né la routine notturna creano, chiudono
  o modificano qualcosa su ClickUp.
- **Una riga per task**, nel formato descritto in `.claude/skills/task-sync/SKILL.md` (il
  commento `<!-- cu:… -->` in fondo alla riga è ciò che il briefing confronta da un giro
  all'altro).
- **Ogni numero si ricalcola dalla fonte**, non si ricopia dal giro prima: conteggi e date
  compresi.

Entrambe le cartelle nascono al primo uso: se non le vedi, va bene così.

## Chiudere una task

- **Nel Cruscotto:** spunti la card e la task si chiude sulla sua fonte (ClickUp, Promemoria o
  il file del vault). La spunta è la tua conferma.
- **In chat:** `/task-sync`. Claude ti mostra cosa sta per chiudere, aspetta il tuo sì, esegue e
  lo scrive in `audit-log.md`.
- La routine notturna non chiude mai nulla.

## Formato: sottotask

Una **sottotask** è una riga `- [ ]` rientrata di **4 spazi** sotto la task madre; il Cruscotto
legge la gerarchia dal rientro. Altre convenzioni (primo tag = progetto, note sotto la task,
priorità dei promemoria): `.claude/apps/cruscotto/README.md`.

## Dove sta la memoria (NON qui)

Le task non sono memoria. Decisioni e stato → `MEMORY.md` dei progetti; conoscenza →
`knowledge/wiki/` e `02-memoria/`.
