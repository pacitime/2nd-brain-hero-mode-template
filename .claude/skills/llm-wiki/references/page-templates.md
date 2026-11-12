# Template delle pagine wiki (struttura PIATTA)

> I template per le pagine del wiki. Tutte le pagine stanno dritte in `wiki/`, il tipo nel
> frontmatter. Copia il blocco giusto e riempilo. Provenienza obbligatoria su ogni affermazione.

---

## Sintesi fonte (type: source)

File: `AAAA-MM-GG-titolo-kebab.md`

```markdown
---
title: "Titolo della fonte"
type: source
created: AAAA-MM-GG
updated: AAAA-MM-GG
sources: [AAAA-MM-GG-titolo-kebab]   # stesso stem del file in raw/
source_url: "https://..."
author: "Autore"
publication_date: AAAA-MM-GG
tags: []
---

# Titolo della fonte

## Sintesi
[2-3 paragrafi: di cosa tratta, perché conta.]

## Claim chiave
- Claim 1 (con contesto)
- Claim 2 (con contesto)

## Entità menzionate
- [[nome-entità]]: ruolo/rilevanza nella fonte

## Concetti trattati
- [[nome-concetto]]: come si collega

## Citazioni notevoli
> "Citazione" (contesto)

## Note
[Osservazioni, collegamenti ad altra conoscenza del wiki.]
```

---

## Sintesi fonte: call registrata (type: source)

File: `AAAA-MM-GG-call-descrizione.md` (la fonte grezza sta in `knowledge/calls/`)

```markdown
---
title: "Call: <descrizione>"
type: source
created: AAAA-MM-GG
updated: AAAA-MM-GG
call_date: AAAA-MM-GG
partecipanti: [nome-1, nome-2]
sources: [AAAA-MM-GG-call-descrizione]   # stesso stem del file in ../calls/
tags: []
---

# Call: <descrizione> (AAAA-MM-GG)

## Sintesi
[2-3 paragrafi.]

## Punti decisi / da decidere
- [ ] <punto aperto> → proporre in MEMORY.md (decisione umana)

## Azioni emerse (proposte, non eseguite)
- <azione> → candidata a task ClickUp / tasks/ (l'utente approva)

## Entità menzionate
- [[nome-entità]]: ruolo

## Concetti trattati
- [[nome-concetto]]: collegamento

## Citazioni / dati
> "..." (contesto)
```

---

## Entità (type: entity)

File: `nome-entita-kebab.md`

```markdown
---
title: "Nome Entità"
type: entity
created: AAAA-MM-GG
updated: AAAA-MM-GG
sources: [nome-fonte-1]
related: [[entità-collegata]], [[concetto-collegato]]
tags: []
---

# Nome Entità

## Panoramica
[1-2 paragrafi.]

## Fatti chiave
- <fatto> [da: [[fonte]]]

## Rilevanza
[Perché conta per noi.]

## Correlati
- [[entità-collegata]]: relazione

## Storico fonti
- [[fonte-1]]: cosa ha aggiunto
```

---

## Concetto (type: concept)

File: `nome-concetto-kebab.md`

```markdown
---
title: "Nome Concetto"
type: concept
created: AAAA-MM-GG
updated: AAAA-MM-GG
sources: [nome-fonte-1]
related: [[concetto-collegato]]
tags: []
---

# Nome Concetto

## Definizione
[Netta e concisa.]

## Come funziona
[Meccanismo o pattern.]

## Punti chiave
- Punto 1 [da: [[fonte]]]

## Applicazioni
[Dove/come si usa nel nostro caso.]

## Correlati
- [[concetto-collegato]]: come si lega
```

---

## Confronto (type: comparison)

File: `tema-a-vs-tema-b.md`

```markdown
---
title: "Tema A vs Tema B"
type: comparison
created: AAAA-MM-GG
updated: AAAA-MM-GG
comparing: [[tema-a]], [[tema-b]]
sources: [nome-fonte-1]
tags: []
---

# Tema A vs Tema B

## Sintesi
[1-2 paragrafi.]

## Differenze chiave
| Dimensione | Tema A | Tema B |
|-----------|--------|--------|
| [Dim 1] | [A] | [B] |

## Quando usare l'uno o l'altro
**Tema A quando:** ...
**Tema B quando:** ...

## Trade-off
[Sfumature, casi limite.]
```
