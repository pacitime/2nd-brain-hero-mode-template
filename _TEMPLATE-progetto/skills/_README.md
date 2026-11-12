# skills/: le skill di questo progetto

> Una skill è una procedura scritta che l'assistente segue da solo quando gli chiedi quella
> cosa («fammi il report del mese», «prepara il preventivo»). Le skill di un solo progetto
> vivono qui, dentro il progetto, così viaggiano con lui.

## Quando crearne una

Solo per una procedura che si ripete davvero (almeno tre volte, o ogni settimana o mese) e che
ha passi fissi. Una cosa fatta una volta resta una riga in `references/metodo.md`.

## Come è fatta

Una sottocartella per skill, con il nome `<progetto>-<compito>` e dentro un file `SKILL.md`:

```
skills/
  progetto-esempio-report-mensile/
    SKILL.md
```

Il `SKILL.md` comincia con il nome e la descrizione (quando usarla, con le frasi che la fanno
partire), poi i passi.

## Come la trova Claude Code

Claude Code cerca le skill solo in `.claude/skills/`. Per ogni skill del progetto si crea lì un
collegamento simbolico (un rimando, non una copia). Dalla radice del vault:

```
ln -s ../../<path>/skills/<nome> .claude/skills/<nome>
```

dove `<path>` è la cartella del progetto come scritta in `.claude/config/brain.json`. Per
esempio: `ln -s ../../10-lavoro/progetto-esempio/skills/progetto-esempio-report-mensile .claude/skills/progetto-esempio-report-mensile`.

Non devi farlo tu: chiedi all'assistente «crea la skill per ...» e la prepara con il
collegamento. Poi aggiungi una riga nella sezione «Skill del progetto» di `references/metodo.md`.

Quando nomini il progetto in chat, l'assistente vede da solo l'elenco delle skill di questa
cartella.
