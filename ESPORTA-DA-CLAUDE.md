# Passo 0: fatti consegnare da Claude quello che sa già di te

> Se usi già Claude (o un altro assistente) da un po', sa molte cose su di te e sui tuoi
> progetti. Invece di riscriverle da zero, fattele consegnare in un documento. Dieci minuti
> qui ti fanno risparmiare ore dopo.

## Come si fa

1. Apri **claude.ai** (o l'app di Claude), nella chat normale, quella che usi di solito.
2. Incolla il prompt qui sotto e invia.
3. Quando ha finito, scarica il documento o copia tutto il testo.
4. Salvalo nella cartella `00-inbox/` del vault, con il nome `export-claude.md`.
5. **Se usi i Progetti di Claude**, ripeti dentro ogni Progetto: ognuno ha la sua conoscenza.
   Salva i file come `export-claude-<nome-progetto>.md`, sempre in `00-inbox/`.

Usi ChatGPT o un altro assistente? Lo stesso prompt funziona anche lì: salva il risultato in
`00-inbox/` allo stesso modo.

Prima di salvare, dai una letta: se trovi qualcosa che non vuoi nel vault (dati di salute,
questioni private di altre persone, password), cancellalo dal documento.

## Il prompt da incollare

```
Sto costruendo un archivio personale su file (un "second brain") e voglio partire da quello
che sai già di me. Usa tutto ciò a cui hai accesso: la tua memoria, le conversazioni passate
che riesci a cercare, i file e le istruzioni di questo Progetto se siamo dentro un Progetto.
Cerca davvero nelle conversazioni passate, non limitarti a quello che ricordi a prima vista.

Scrivi UN SOLO documento Markdown, completo, con queste sezioni. Se per una sezione non sai
nulla scrivi "Nessuna informazione": non inventare e non riempire.

# 1. Chi sono
Nome, dove vivo, lingua, lavoro che faccio, come descrivo quello che faccio.

# 2. Come lavoro e cosa preferisco
Come voglio le risposte (lunghezza, tono, formato). Cose che mi danno fastidio. Regole che ti
ho dato più volte. Strumenti e app che uso e a cosa mi servono (solo i nomi, mai password).

# 3. I miei progetti
Una sottosezione per OGNI progetto, cliente o attività di cui abbiamo parlato. Per ciascuno:
- Cos'è, in due righe, e per chi
- Stato attuale
- Persone coinvolte e ruolo di ciascuna
- Decisioni prese, con la data se la conosci e il motivo
- Questioni ancora aperte
- Fatti e numeri importanti (prezzi, offerta, risultati, scadenze)
- Posizionamento e tono di voce, se ne abbiamo parlato
- Come lavoriamo: procedure che ripeto, formati delle consegne, strumenti, chi fa cosa,
  errori che abbiamo già fatto e non vanno ripetuti
- Parole e nomi che compaiono quasi solo quando parlo di questo progetto

# 4. Società, contratti, questioni fiscali
Solo la struttura e le decisioni: quali società o partite IVA esistono, a cosa servono,
consulenti che seguo, scadenze note. Niente coordinate bancarie, niente credenziali.

# 5. Vita personale
Solo ciò che riguarda l'organizzazione: viaggi, casa, sport, impegni ricorrenti. Lascia fuori
i dati di salute e le questioni private di altre persone.

# 6. Obiettivi
Dove sto cercando di arrivare nei prossimi mesi, e come capirò di esserci arrivato.

# 7. Cose che non sai dove mettere
Tutto ciò che ricordi di me e non rientra sopra.

Regole:
- Scrivi solo ciò che risulta davvero dalle nostre conversazioni o dalla tua memoria.
- Quando non sei sicuro, aggiungi "[da verificare]" accanto alla frase.
- Quando conosci la data di una decisione, scrivila. Quando non la conosci scrivi "[data non nota]".
- Sii completo: meglio un documento lungo che uno riassunto. Non accorciare per brevità.
- Consegna il documento come file scaricabile se puoi, altrimenti in un unico blocco di testo.
```

## E se non ho mai usato Claude?

Nessun problema: salta questo passo. Il primo avvio ti farà una breve intervista e il vault si
riempirà con l'uso.
