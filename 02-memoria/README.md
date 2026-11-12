---
tipo: contenitore-memoria
---

# 02-memoria: memoria long-term globale

> La memoria long-term **non è una capacità del modello: è ciò che è scritto su disco**
> (`CAPISALDI.md` §1). Qui sta la parte **globale**, quella che non appartiene a un singolo
> progetto. I progetti hanno il loro `MEMORY.md` e il loro `knowledge/wiki/`.

## Cosa c'è dentro
- **`me.md`**: chi sei, preferenze, principi. È il nucleo, una riga per regola.
- **`OBIETTIVI.md`**: obiettivi attivi, riletti al briefing e alla review settimanale.
- **`SOUL.md`**: la voce e i confini con cui l'assistente lavora.
- **`PROMOTE-QUEUE.md`**: i candidati memoria in attesa. Si smaltisce con `promote-triage`.
- **`PROMOTE-ARCHIVIO.md`**: i dubbi veri fermi da più di 30 giorni. Non caricato.
- **`wiki/`**: insight **trasversali** ai progetti e le pagine `me-*` con il testo completo
  delle regole su di te. Indice in `wiki/index.md`, convenzioni in `wiki/SCHEMA.md`.

## Come ci arriva la roba
Call e sessioni producono **candidati** → `PROMOTE-QUEUE` → il tier sicuro si promuove da
solo, i dubbi aspettano te → la memoria viene scritta nella destinazione giusta (una pagina
`me-*`, il `wiki/`, o il `MEMORY.md` di un progetto).

## Dove si perde davvero la memoria
Non fra un'app e l'altra: **fra la conversazione e il disco**. Un candidato che resta in coda
è invisibile a ogni sessione futura, come se non fosse mai stato catturato. Catturare senza
smaltire non è memoria, è un magazzino. Quando «non si ricorda», la mossa è smaltire la coda.

## La memoria automatica di Claude Code: cosa può contenere
Claude Code ha una sua cartella di memoria fuori dal vault, caricata a ogni avvio. **Non è una
seconda copia di `me.md`**: se ne duplicasse il contenuto ci sarebbero due verità che
divergono. Lì stanno solo pochi puntatori al vault e abitudini di lavoro spicciole. Nessun
dato personale: quella cartella è fuori dal vault, quindi fuori dal backup e dalle protezioni
degli hook, e non arriva nelle sessioni cloud.
