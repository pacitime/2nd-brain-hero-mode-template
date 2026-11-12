---
tipo: progetto
aggiornato: AAAA-MM-GG
---

# <NOME PROGETTO>

> Identità e stato del progetto. È la prima pagina che Claude legge quando gli chiedi di
> lavorarci. Per creare un progetto: copia tutta la cartella `_TEMPLATE-progetto/` dentro
> `10-lavoro/`, rinominala, e aggiungi il progetto a `.claude/config/brain.json`.

## Cos'è
<Una o due frasi: cosa fa questo progetto, per chi.>

## Stato
<La fase attuale in una riga. La storia delle decisioni sta in `MEMORY.md`.>

## Società collegata
> Il progetto non è la società che fattura. Il legame è questa riga.

- Società: <nome, con link alla cartella in `20-fiscale-legale/`, oppure «da definire»>

## Persone
- <Nome>: <ruolo>

## 🔓 Loop aperti
> **Obbligatoria in ogni progetto** (`CLAUDE.md` §9). È la sezione che il briefing sorveglia e
> che call, email e documenti nuovi aggiornano da soli. Qui stanno le questioni aperte, non le
> task operative. Si chiude un loop solo su evidenza, con data e fonte.
> Se è vuota si scrive `_Nessun loop aperto._`: la sezione non si cancella.

_Nessun loop aperto._

## 🧭 Metodo e skill
> Come si lavora qui sta in `references/metodo.md`: procedure, formati, errori da non ripetere.
> Quando nomini il progetto in chat, l'assistente lo carica da solo insieme agli essenziali, ai
> titoli dei loop aperti e all'elenco delle skill.

- Metodo → `references/metodo.md`
- Skill del progetto → `skills/` (come crearne una: `skills/_README.md`)

## Link rapidi
- Decisioni e stato → `MEMORY.md`
- Essenziali sempre caricati → `references/`
- Conoscenza distillata → `knowledge/wiki/index.md`
- Call → `knowledge/calls/`
- Task strategiche → `tasks/aperti.md`
