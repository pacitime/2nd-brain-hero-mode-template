# HEARTBEAT.md: cosa controlla l'assistente

> Elenco di ciò che l'assistente controlla quando gli chiedi il **briefing** (`/heartbeat`).
> L'assistente **propone, non agisce**: bozze e candidati, mai invii o creazioni senza il tuo ok.
> Orari attivi **8:00-19:00** (cambiali come preferisci); fuori orario, silenzio salvo urgenze.

## Controlli rapidi (a ogni briefing)
- **Calendario** oggi + prossime ore: eventi, e preparazione mancante per le call.
- **Task ClickUp assegnate a te**, nei workspace configurati in `.claude/config/brain.json`:
  scadute, in scadenza, prioritarie ⏫.
- **Email importanti** (gli account configurati in Apple Mail): non lette che richiedono risposta.
- **Call recenti** in `00-inbox/calls/`: da smistare/distillare.
- **Coda promote** (`02-memoria/PROMOTE-QUEUE.md`): candidati in attesa.
- **Daily** ieri/oggi: cosa è successo di rilevante.

## Suggerimenti proattivi
- Cosa mettere in cima **ora**, viste scadenze e calendario.
- Cosa in arrivo ha bisogno di **preparazione** e non ce l'ha.
- Task scadute che richiedono un'azione precisa (riprogramma / delega / cancella).
- In base all'ora, cosa è utile suggerire.

## Anomalie (segnala se fuori dal solito)
- **Picco** di mail non lette rispetto al solito.
- **Meeting spostati/cancellati** non attesi.
- **Task scadute da più di una settimana** (ferme: proponi una pulizia).

## Manutenzione della memoria (giornaliera)
- Rivedi il **daily di ieri**.
- Estrai ciò che vale → **proponi candidati in `PROMOTE-QUEUE`** (mai scrivere in `MEMORY`/`me.md` di sua iniziativa).

## Priorità: cosa mettere in cima
1. **Urgenze di oggi** (mail urgente da un contatto importante · call entro 2 ore senza preparazione · task scadute).
2. **Email** che richiedono risposta.
3. **Preparazione** delle call imminenti.
4. Task **scadute**.
5. Il resto (raggruppato).

## Bozze (`drafts/`): SOLO su richiesta
- L'assistente prepara bozze in `drafts/active/` **quando gliele chiedi**; **non** ne scrive di
  sua iniziativa.
- Voce da `SOUL.md` + `me.md` + `references/`. **Invio sempre a mano.**

## Cosa NON fa
- Non invia. Non crea/chiude task senza ok.
- Non tocca gli account che hai scelto di tenere fuori dall'AI (per esempio quello bancario o
  quello strettamente personale).
- Niente chat di team, social o community: solo le fonti elencate sopra.
- Il briefing parte quando lo chiedi, non di sua iniziativa.

---
_Ritoccalo quando vuoi: è la configurazione del briefing. Si affina osservando cosa ti è utile._
