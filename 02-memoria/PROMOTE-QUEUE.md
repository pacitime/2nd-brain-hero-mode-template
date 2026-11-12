# PROMOTE-QUEUE: candidati alla memoria

> **A cosa serve.** Quando l'agente, in una sessione, vede qualcosa che varrebbe la pena
> ricordare (una decisione, una lezione, un fatto durevole), NON lo scrive in memoria: lo
> **aggiunge qui come candidato**.
>
> **Come si smaltisce.** Con `/promote-triage`, quando lo chiedi tu (e ogni notte, se attivi la
> routine cloud). Il **tier sicuro** (fatti, lezioni e decisioni chiare che passano la verifica
> su disco) viene scritto nella destinazione e registrato in `audit-log.md`, reversibile con
> Git. Restano **in coda per te** solo i **dubbi**: ambigui, decisioni ancora aperte, doppioni,
> progetto mancante, dati personali.
>
> **Invariante: promuovere non è smaltire.** Una voce scritta in destinazione ma lasciata qui
> diventa un fantasma indistinguibile dai candidati veri. Chi scrive in memoria sposta la voce
> nello stesso giro.
>
> **Destinazioni possibili:** `MEMORY.md` di un progetto · una pagina `me-*` o un'altra pagina
> del wiki globale · una pagina del wiki di progetto. Il candidato dice quale.

---

## Rituale di recap (quando lo chiedi, o alla review settimanale)

1. L'agente legge questa coda e ti presenta **un candidato alla volta**: testo proposto,
   destinazione, fonte.
2. Tu rispondi **Approva** / **Modifica** (detti la correzione) / **Scarta** (motivo breve).
3. Su *Approva*: scrive il testo nella destinazione vera e sposta la voce in *Promossi*.
4. Su *Scarta*: la sposta in *Scartati* con il motivo, così non te la ripropone.

---

## In attesa

<!--
L'agente AGGIUNGE qui i candidati con questo formato:

### [AAAA-MM-GG] <tipo: decisione|lezione|fatto> → <destinazione>
**Proposta:** <testo conciso, già pronto da incollare in memoria>
**Fonte:** <file in raw/ o calls/, o "sessione chat AAAA-MM-GG">
**Stato:** da rivedere
-->

_Nessun candidato in coda._

---

## Promossi (storico)

_Ancora nessuno._

## Scartati (storico breve)

_Ancora nessuno._
