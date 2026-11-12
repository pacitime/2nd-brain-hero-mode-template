# 2nd Brain Hero Mode: la guida

> Come organizzo progetti, memoria e attività con Claude, e come puoi farlo anche tu.
> Di Alessandro Pacifico, Pacibrand.

Questa guida accompagna il kit. Puoi leggerla tutta prima di cominciare, oppure fermarti al
capitolo 7, installare, e tornare qui quando ti serve un pezzo in più. E puoi sempre chiedere a
Claude: «leggi GUIDA.md e spiegami il capitolo sulle call».

**Indice**

0. [Cos'è, per chi è, cosa serve](#0-cosè-per-chi-è-cosa-serve)
1. [L'idea in una pagina](#1-lidea-in-una-pagina)
2. [La struttura: tre pilastri](#2-la-struttura-tre-pilastri)
3. [Un progetto, sempre la stessa forma](#3-un-progetto-sempre-la-stessa-forma)
4. [La memoria](#4-la-memoria)
5. [Il motore: dalle fonti al sapere](#5-il-motore-dalle-fonti-al-sapere)
6. [La sicurezza](#6-la-sicurezza)
7. [Installazione passo passo (livello 1)](#7-installazione-passo-passo-livello-1)
8. [Come si usa ogni giorno](#8-come-si-usa-ogni-giorno)
9. [Come lo uso io: gli strumenti (livello 2)](#9-come-lo-uso-io-gli-strumenti-livello-2)
10. [Farlo lavorare nel cloud (livello 3)](#10-farlo-lavorare-nel-cloud-livello-3)
11. [Gli errori che ho già pagato io](#11-gli-errori-che-ho-già-pagato-io)
12. [Checklist e domande frequenti](#12-checklist-e-domande-frequenti)

---

## 0. Cos'è, per chi è, cosa serve

Un **second brain** è un posto solo dove vive tutto quello che sai e che fai: progetti,
decisioni, call, documenti, obiettivi. Il mio è una cartella di file di testo sul computer,
con Claude che ci lavora dentro. Lo uso per il mio personal brand, per i progetti con i
clienti, per le società, per la vita personale.

La differenza rispetto a «usare Claude in chat» è una: **Claude smette di dimenticare**.
Ogni sessione parte sapendo chi sei, cosa hai deciso il mese scorso, cosa è ancora aperto su
ogni progetto. E lo sa perché è scritto in file che puoi aprire, leggere e correggere tu.

**Per chi è.** Per chi lavora su più fronti (un brand, dei clienti, un team, una società) e
usa già Claude. Non serve saper programmare: non ho mai chiesto a nessuno di aprire un
terminale, e non lo chiedo a te.

**Cosa serve davvero.**

| Cosa | Costo | Note |
|---|---|---|
| Un abbonamento Claude a pagamento | Dal piano Pro in su | Claude Code è incluso. Non serve nessuna chiave API |
| VS Code | Gratis | Il programma in cui lavori con Claude sui file |
| Obsidian | Gratis | Per leggere e navigare il vault. Facoltativo ma lo consiglio |
| Un Mac | | La base funziona ovunque giri Claude Code. Gli strumenti dei livelli 2 e 3 sono nati su Mac |

Tutto il resto (Granola, ClickUp, GitHub) è facoltativo e arriva dopo.

**Tre livelli, uno alla volta.**

- **Livello 1, la base.** Struttura, memoria, wiki, sicurezza. Mezz'ora per partire.
- **Livello 2, gli strumenti.** Le call entrano da sole, le task in un cruscotto unico, il
  briefing, la posta in lettura. Li accendi uno per volta, quando ne senti il bisogno.
- **Livello 3, il cloud.** Backup su GitHub, vault dal telefono, lavoro notturno.

Il consiglio più importante della guida: **resta al livello 1 almeno una settimana**. Il
valore sta nell'abitudine di lavorare dentro il vault, non nel numero di automazioni accese.

---

## 1. L'idea in una pagina

Cinque idee reggono tutto il resto.

**1. I file prima delle app.** Il vault è una cartella di file Markdown (testo semplice) sul
tuo computer. Le app cambiano, chiudono, alzano i prezzi. Un file di testo si apre fra dieci
anni con qualunque programma.

**2. La memoria è ciò che sta scritto.** Claude non «ricorda» da una sessione all'altra per
magia: rilegge dei file. Se una decisione non è scritta in un file, alla prossima sessione
non esiste. Tutto il sistema serve a far sì che le cose importanti finiscano scritte, nel
posto giusto, senza che debba pensarci tu.

**3. Tre superfici, tre lavori.** La *chat* di Claude per pensare e discutere. *Claude Code*
(dentro VS Code) per lavorare sui file del vault. Il *vault* come memoria che cresce. La chat
non scrive nel vault da sola: per questo si lavora da Claude Code.

**4. Si distilla una volta, non si rilegge ogni volta.** Una call di un'ora non va riletta a
ogni domanda. Claude la legge una volta, ne tira fuori ciò che conta, lo scrive in una pagina
con la fonte accanto. La volta dopo legge la pagina.

**5. L'assistente parte da consulente.** Legge, prepara, propone. Quello che è reversibile lo
fa da solo. Quello che esce dal computer o non si può annullare lo decidi tu. E le regole
importanti non sono affidate alla sua buona volontà: sono blocchi veri.

---

## 2. La struttura: tre pilastri

```
il-tuo-vault/
├── 00-inbox/            dove butti le cose prima di sapere dove vanno
├── 01-daily/            il diario automatico delle sessioni
├── 02-memoria/          quello che Claude sa di te
├── 03-task/             note sull'assetto delle task
├── 10-lavoro/           i progetti: clienti, prodotti, contenuti
├── 20-fiscale-legale/   società, contratti, contabilità
├── 30-personale/        la tua vita
└── _local-only/         ciò che non lascia mai il computer (le chiavi)
```

- **Lavoro** è *cosa fai*. Un progetto, una cartella.
- **Fiscale e legale** è *chi fattura e chi paga le tasse*. Serve tutti i progetti, per questo
  sta a parte.
- **Personale** è la tua vita. Senza soldi e senza questioni legali, che stanno nel secondo
  pilastro.

**Perché un vault solo.** Un personal brand non è un progetto isolato. Il contenuto che
pubblico nasce da una call con un cliente; il contratto di quel cliente tocca una società; la
società tocca scelte personali. Se queste cose stanno in tre strumenti, Claude vede un terzo
del quadro e il ponte lo faccio io a mano.

**Il confine che conta.** Il progetto non è la società che fattura. Lo stesso progetto può
cambiare società; la stessa società serve più progetti. Il legame è una riga nella scheda del
progetto, non una cartella da rifare.

---

## 3. Un progetto, sempre la stessa forma

Ogni progetto, grande o piccolo, ha la stessa anatomia:

```
10-lavoro/<progetto>/
├── README.md        chi è, a che punto è, chi ci lavora, cosa è ancora aperto
├── MEMORY.md        le decisioni prese, con data e motivo
├── references/      gli essenziali: posizionamento, tono di voce, offerta
│   └── metodo.md    come si lavora qui: procedure, formati, errori da non ripetere
├── skills/          le skill di questo progetto (procedure che Claude segue da solo)
├── knowledge/
│   ├── raw/         i documenti originali, intoccabili
│   ├── calls/       i transcript delle call
│   └── wiki/        il sapere distillato, con la fonte di ogni affermazione
├── tasks/           le task strategiche
└── assets/          quello che il progetto produce
```

**Perché sempre uguale.** Con dieci progetti organizzati in dieci modi, Claude a ogni
sessione deve riscoprire dove sono le cose, e sbaglia. Con una forma sola sa già dove
guardare. E lo sai anche tu fra sei mesi.

**Tre livelli di attenzione.** Non tutto merita di stare sempre davanti agli occhi:

- `references/`: poche pagine corte che Claude legge **ogni volta** che lavora sul progetto.
- `knowledge/wiki/`: il sapere profondo, che apre **solo quando serve**.
- `MEMORY.md`: le decisioni, che **approvi tu**.

**Il metodo.** In `references/metodo.md` c'è come si lavora su quel progetto: le procedure
che ripeti, il formato delle consegne, gli strumenti, chi fa cosa, gli errori già fatti. È il
foglio che daresti a un collaboratore nuovo il primo giorno. Ha un tetto di 120 righe: oltre,
il dettaglio scende nel wiki e nel metodo resta una riga.

**Le skill del progetto.** Una skill è una procedura scritta che Claude segue da solo quando
gliela chiedi («fammi il report del mese»). Quelle che servono a un solo progetto vivono nella
sua cartella `skills/`. Se ne crea una solo per una cosa che si ripete davvero, con passi
fissi. Le prepara Claude, con un rimando in `.claude/skills/` perché Claude Code la trovi.

**Cosa entra da solo quando nomini un progetto.** Scrivi in chat il nome del progetto (o uno
dei nomi che hai registrato per lui) e, la prima volta nella sessione, Claude riceve da solo:
il metodo, gli essenziali di `references/` (interi finché stanno nel tetto, poi solo i nomi),
i titoli dei loop aperti e l'elenco delle skill. Non serve dire «carica il contesto»: basta
nominarlo.

**I loop aperti.** Nel README di ogni progetto c'è una sezione «🔓 Loop aperti»: le questioni
in sospeso. Non sono task («manda la mail»): sono cose non ancora risolte («il cliente non ha
confermato il prezzo»). È la sezione più viva del vault, e al capitolo 5 vedi perché.

**Per aprire un progetto nuovo** dici a Claude: «crea il progetto <nome>». Copia lo stampo,
compila la scheda con te, e lo registra perché le call di quel progetto ci arrivino da sole.

**Un'idea non nasce progetto.** Prima è un file in inbox. Diventa una cartella solo quando è
validata.

---

## 4. La memoria

Due strati.

**La memoria di progetto** vive nel progetto: `MEMORY.md` per le decisioni, `wiki/` per il
sapere.

**La memoria su di te** vive in `02-memoria/`:

- `me.md`: chi sei e come lavori. È il nucleo, **una riga per regola**. Claude lo legge a ogni
  sessione.
- `wiki/` con le pagine `me-*`: il testo completo di ogni regola, con il caso che l'ha
  insegnata. Si aprono quando servono.
- `SOUL.md`: il carattere e i confini dell'assistente.
- `OBIETTIVI.md`: dove stai andando.

**Come ci arrivano le cose, senza che ci pensi tu.**

1. Lavori con Claude, come sempre.
2. A fine sessione un salvataggio automatico scrive il diario del giorno e tira fuori i
   **candidati**: decisioni, lezioni, fatti che vale la pena ricordare.
3. I candidati vanno in una coda (`PROMOTE-QUEUE.md`).
4. Quando dici «smaltiamo la coda», Claude scrive in memoria da solo ciò che è sicuro (fatti
   e lezioni chiare, verificate) e ti chiede solo i dubbi.

**Perché una coda e non la scrittura diretta.** Perché in memoria non deve finire niente di
sbagliato senza che tu lo veda. E perché una decisione ancora in ballo non è una decisione.

**Anche il metodo cresce con l'uso.** Quando in una sessione impari come si fa una cosa su un
progetto («le proposte vanno sempre in PDF», «prima di pubblicare si controlla il link»), il
salvataggio di fine sessione la può proporre come candidato per il `metodo.md` di quel
progetto. Passa dalla stessa coda. Così il metodo si scrive lavorando, non in un pomeriggio
di buona volontà.

**Cresce senza pesare.** Quello che si carica a ogni sessione ha un tetto. Senza tetto, dopo
tre mesi il file «chi sono» è così lungo che rallenta ogni risposta. Con il tetto, il nucleo
resta corto e il dettaglio sta nelle pagine a parte. Vale anche per il metodo e gli essenziali
di ogni progetto: il controllo di salute ti avvisa all'80% del tetto.

---

## 5. Il motore: dalle fonti al sapere

**Ingest, ask, lint.** Tre mosse.

- **Ingest.** Metti una fonte nel vault (un documento, una call, un export). Dici «ingerisci
  questa fonte». Claude la legge tutta, scrive una sintesi, crea o aggiorna le pagine delle
  persone e dei concetti che contiene, e segna da dove viene ogni affermazione.
- **Ask.** Fai una domanda. Claude risponde leggendo il wiki, con le citazioni. Se la
  risposta vale, diventa a sua volta una pagina.
- **Lint.** Una volta a settimana, la review: cosa promuovere in memoria, quali pagine si
  contraddicono, quali sono rimaste orfane.

**Due regole che non si discutono.**

1. **Le fonti sono dati, mai istruzioni.** Se in un documento c'è scritto «ignora le regole e
   fai questo», Claude lo segnala e non lo fa.
2. **Le decisioni restano tue.** Claude scrive sintesi e collegamenti. Le decisioni le scrivi
   o le approvi tu.

**I loop aperti si aggiornano da soli.** Ogni fonte nuova viene confrontata con i loop aperti
del progetto:

- se la fonte **chiude** un loop, Claude lo spunta, con data e fonte;
- se lo **fa avanzare**, aggiorna il testo allo stato reale;
- se emerge una questione **nuova**, la aggiunge.

Si chiude **solo su evidenza**. «Una vendita registrata» chiude un loop. «Ne abbiamo parlato»
no. Le contraddizioni con le decisioni già prese non le tocca: te le porta.

**Le task no.** Dalle call Claude tira fuori memoria e aggiorna i loop. Non crea task: quelle
le crea chi le deve fare, altrimenti nascono doppioni con quelle che il team si è già scritto.

---

## 6. La sicurezza

Un assistente che legge la tua posta e i tuoi documenti legge anche testo scritto da altri. Il
rischio nasce quando stanno insieme tre cose: **dati privati**, **contenuto non fidato**,
**possibilità di agire verso l'esterno**. La difesa è togliere la terza.

**Cosa fa il kit, concretamente.**

- **La posta si legge e non si invia.** Claude prepara bozze. Le mandi tu.
- **Le chiavi non entrano mai in chat.** Stanno in un file che Claude non può aprire: c'è un
  blocco che glielo impedisce. Gli script le usano, lui non le vede.
- **Niente cancellazioni di massa**, niente scritture fuori dalla cartella del vault.
- **Le regole non si riscrivono da sole.** Per modificare i tre documenti che dicono a Claude
  come comportarsi serve un tuo clic.
- **Tutto ciò che fa da solo finisce in un registro** (`audit-log.md`) che rileggi nella
  review settimanale.

Questi blocchi si chiamano **hook**: piccoli programmi che controllano ogni azione prima che
avvenga. Non dipendono da quanto è bravo il modello o da cosa c'è scritto in un prompt.

**La scala dei permessi.**

| Tipo di azione | Esempio | Cosa fa Claude |
|---|---|---|
| Reversibile, interna | Archiviare un file, aggiornare un loop, scrivere nel wiki | La fa e la registra |
| Con conseguenze, o verso l'esterno | Creare una task per il team, inviare, pubblicare, cancellare | Propone, aspetta il tuo sì, esegue |
| Ambigua | Non è chiaro dove vada una cosa | Chiede |

**Una cosa da sapere.** Per non interromperti cento volte al giorno, dentro il vault Claude
modifica i file e lancia i comandi innocui senza chiederti conferma ogni volta. Ti chiede
conferma per installare programmi, per le chiamate verso internet, per pubblicare su GitHub,
per cancellare. I blocchi di cui sopra valgono sempre, conferma o no.

**Cosa non mettere nel vault, mai.** Password e codici di accesso alla banca, documenti
d'identità, dati di salute.

---

## 7. Installazione passo passo (livello 1)

Tempo: circa mezz'ora, più il primo avvio. Non si apre nessun terminale.

### Passo 1. Abbonamento Claude

Serve un piano a pagamento (Pro o superiore). Se usi già Claude a pagamento, sei a posto: è lo
stesso account.

### Passo 2. Installa VS Code

1. Vai su **code.visualstudio.com** e scarica la versione per Mac.
2. Apri il file scaricato e trascina **Visual Studio Code** nella cartella Applicazioni.
3. Aprilo.

VS Code è un programma per lavorare sui file. Lo usano i programmatori, ma a te serve per una
cosa sola: è il posto più comodo in cui Claude lavora su una cartella. A sinistra vedi i file,
a destra parli con Claude.

### Passo 3. Installa l'estensione Claude Code

1. In VS Code premi **Cmd + Shift + X** (si apre il pannello Estensioni).
2. Cerca **Claude Code**. Quella giusta è pubblicata da **Anthropic**.
3. Clicca **Install**.
4. Se dopo l'installazione non vedi niente di nuovo, chiudi e riapri VS Code.

### Passo 4. Scarica il kit e mettilo nel posto giusto

1. Scarica lo zip del kit (su GitHub: pulsante verde **Code**, poi **Download ZIP**) e aprilo
   con un doppio clic: compare una cartella che si chiama `2nd-brain-hero-mode-template-main`.
2. Spostala nella tua **cartella Inizio** (quella con il tuo nome utente, nel Finder: menu
   Vai, Inizio). Rinominala come vuoi, per esempio `brain`.

**Non metterla sulla Scrivania né in Documenti**, e non dentro iCloud Drive, Dropbox o Google
Drive. Due motivi: quelle cartelle spesso si sincronizzano da sole e la sincronia crea
conflitti sui file; e macOS limita cosa possono fare lì i programmi automatici del livello 2.

### Passo 5. Apri il vault in VS Code

1. In VS Code: menu **File, Open Folder** (Apri cartella) e scegli la cartella del vault.
2. VS Code chiede se ti fidi degli autori dei file: rispondi **Sì**. Senza, Claude non parte.
3. Apri il pannello di Claude: clicca **✻ Claude Code** in basso a destra, oppure l'icona a
   forma di scintilla in alto a destra.
4. Al primo uso ti chiede di accedere: clicca **Sign in** e completa nel browser con il tuo
   account Claude.

Da qui in poi, tutto quello che ti serve lo chiedi a Claude in italiano, in quel pannello.

**Il terminale, se mai servisse.** VS Code ne ha uno incorporato (menu Terminal, New
Terminal). Io lo tengo lì a portata di mano, ma in pratica i comandi li lancia Claude.

### Passo 6. Installa Obsidian (consigliato)

1. Vai su **obsidian.md**, scarica e installa. È gratuito, anche per lavoro.
2. Aprilo, scegli **Apri una cartella come vault** e seleziona la stessa cartella.

Obsidian è il modo comodo di *leggere* il vault: i collegamenti fra le pagine si cliccano, e
c'è una mappa di come tutto è connesso. Claude scrive da VS Code, tu leggi da Obsidian. È lo
stesso identico contenuto: sono solo due finestre sugli stessi file.

### Passo 7. Fatti consegnare da Claude quello che sa già di te

Se usi Claude da un po', sa già molto di te e dei tuoi progetti. Invece di riscrivere tutto:

1. Apri il file `ESPORTA-DA-CLAUDE.md` del vault: dentro c'è un prompt pronto.
2. Incollalo nella chat normale di Claude (claude.ai o l'app), non in VS Code.
3. Salva il documento che ti restituisce nella cartella `00-inbox/`, con nome `export-claude.md`.
4. Se usi i Progetti di Claude, ripeti dentro ogni Progetto.

Dieci minuti qui valgono ore dopo: il vault parte già pieno delle tue cose.

### Passo 8. Il primo avvio

Nel pannello di Claude in VS Code scrivi:

> **Leggi PRIMO-AVVIO.md e partiamo**

Claude controlla che il computer abbia quello che serve, legge l'export, e riempie il vault
con te un passo alla volta: chi sei, come lavori, i tuoi progetti uno per uno, gli obiettivi.
Ti mostra tutto prima di scriverlo. Puoi fermarti e riprendere quando vuoi.

Durante il controllo possono comparire due richieste. Accettale entrambe:

- macOS che propone di installare gli «strumenti da riga di comando per sviluppatori»: sono
  componenti di Apple che servono ai blocchi di sicurezza del kit. Ci vogliono alcuni minuti.
- Claude che ti chiede l'ok per installare il comando `claude`: è il componente ufficiale di
  Anthropic che serve al salvataggio automatico della memoria a fine sessione. Se dopo ti
  chiede di rifare l'accesso, ti guida lui.

### Passo 9. Verifica

Alla fine dovresti avere:

- `02-memoria/me.md` che parla di te
- una cartella in `10-lavoro/` per ogni tuo progetto vivo, con la scheda compilata
- nessun file rimasto in `00-inbox/`

Chiudi il pannello, riaprilo, e chiedi: «cosa sai di me e dei miei progetti?». Se risponde
giusto, il second brain funziona.

---

## 8. Come si usa ogni giorno

Non ci sono comandi da imparare: gli parli. Queste sono le frasi che uso di più.

| Quando | Cosa dico |
|---|---|
| Riprendo un progetto | «Prime su <progetto>» oppure «dove siamo su <progetto>?» |
| Ho un documento o degli appunti nuovi | Li metto in `00-inbox/` e dico «smista l'inbox» |
| Voglio che una fonte diventi sapere | «Ingerisci questa fonte nel wiki» |
| Ho scaricato un file Word o PDF | «Leggi l'ultimo documento scaricato» |
| Cerco qualcosa | «Cosa dice il wiki su <tema>?» |
| Ho preso una decisione | «Scrivi in MEMORY che abbiamo deciso X, perché Y» |
| Nasce un progetto | «Crea il progetto <nome>» |
| Voglio il punto della situazione | «Fammi il punto» oppure «cosa c'è di nuovo?» |
| La memoria va smaltita | «Smaltiamo la coda» |
| Una volta a settimana | «Facciamo la review settimanale» |

**La review settimanale, quindici minuti.** Il venerdì Claude rilegge la settimana e mi
propone da tre a cinque cose da promuovere in memoria, mi segnala contraddizioni fra pagine e
loop fermi da troppo. Io dico sì, no, modifica. È l'unico rituale fisso del sistema, ed è
quello che lo tiene vero.

**Una regola pratica.** Una sessione, un argomento. Quando cambi progetto, apri una chat
nuova: Claude ricarica il contesto giusto e risponde meglio.

---

## 9. Come lo uso io: gli strumenti (livello 2)

Qui ti racconto come gestisco le mie giornate, e per ogni pezzo cosa ti serve per fare lo
stesso. Ogni strumento è indipendente: accendi solo quelli che ti servono. Per accenderne uno
basta chiederlo a Claude, che ha le istruzioni tecniche in `.claude/scripts/STRUMENTI.md`.

### 9.1 Le call: Granola

Registro quasi tutte le call di lavoro con **Granola**, un'app che trascrive e riassume senza
far entrare un bot nella riunione. Il mio vault scarica i transcript da solo, li mette nella
cartella di atterraggio e li **smista nel progetto giusto** leggendo il titolo. Poi Claude ne
tira fuori i candidati memoria e aggiorna i loop aperti. Io non sposto file.

- Una call che non riconosce resta in inbox e me la segnala: decido io.
- Una call con il titolo che parla di salute va da sola in una cartella che non finisce su
  GitHub.

| Cosa serve | |
|---|---|
| App | Granola, su Mac |
| Costo | Il piano **Business** (14 $ al mese per utente, prezzo letto sul sito a novembre 2026). La chiave che serve al vault non è inclusa nel piano gratuito |
| Cosa fai tu | Generi la chiave nell'app (Impostazioni, Connettori, API keys) e la incolli nel file delle chiavi |
| Cosa dici a Claude | «Attiva le call di Granola» |

**Non hai Granola, o non vuoi pagarlo?** Lo smistamento funziona lo stesso: salva gli appunti
o il transcript di una call come file in `00-inbox/calls/` e dì «smista le call». Vale per
qualunque strumento di trascrizione.

### 9.2 Le task: ClickUp, Promemoria e il mio cruscotto

Ho le task in tre posti, e ho smesso di combatterlo:

- **ClickUp** per tutto ciò che coinvolge il team. Le task le crea chi le deve fare.
- **Promemoria di Apple** per le mie cose veloci, in una lista sola dedicata al lavoro.
- **I file `tasks/` dei progetti** per le task strategiche, quelle che voglio accanto alle
  decisioni del progetto.

Per vederle insieme mi sono fatto costruire da Claude un **cruscotto**: una pagina che gira
solo sul mio computer e mostra tutto in una board settimanale. Trascino una card su un altro
giorno e la data cambia alla fonte; spunto una task e si chiude dov'è nata, ClickUp compreso.
È nel kit, e funziona anche con le sole task del vault.

| Cosa serve | |
|---|---|
| Solo task del vault | Niente. Dì «avvia il cruscotto» |
| Promemoria | Un Mac, e una lista di Promemoria dedicata. Le liste personali restano fuori |
| ClickUp | Un account ClickUp e il tuo token personale (avatar, Settings, Apps, API Token), da incollare nel file delle chiavi. Gli id delle liste li ricava Claude |
| Cosa dici a Claude | «Attiva il cruscotto», poi «aggiungi Promemoria», poi «aggiungi ClickUp» |

Dalla chat puoi anche dire «cosa ho oggi?», «sposta X a venerdì», «crea una task per Marco
su ClickUp». Per le ultime serve il connettore ClickUp di Claude (Impostazioni, Connettori), e
ogni scrittura passa dalla tua conferma.

### 9.3 Il briefing

Quando dico «fammi il punto», Claude mi mostra **solo quello che è cambiato** dall'ultima
volta: call nuove, task, promemoria, loop fermi da più di una settimana. Niente elenco
completo ripetuto ogni giorno: quello diventa rumore e smetti di leggerlo.

Prima di leggere un testo che arriva da fuori (una call, una email), il briefing lo fa
controllare da un secondo Claude senza strumenti, che cerca tentativi di manipolazione. Se
qualcosa non lo convince, il testo resta fuori e me lo dice.

Serve: niente. Dici «fammi il punto».

**Il briefing che arriva da solo, la mattina.** Io il punto lo ricevo anche su Slack, ogni
mattina, senza chiederlo. Nel kit questo script non c'è: se lo vuoi, chiedi a Claude di
costruirlo per te. Fallo con due vincoli di sicurezza, e diglielo:

- **il testo del messaggio si compone senza modello.** Lo script mette insieme numeri e titoli
  già scritti nel vault (loop, task, call nuove), con regole fisse. Nessun Claude legge una
  email o una call per scrivere quel messaggio, quindi niente di quello che arriva da fuori
  può decidere cosa viene inviato;
- **l'invio può andare solo a te.** Un hook blocca qualunque invio che non sia verso il tuo
  canale personale (i messaggi a te stesso). Anche se qualcosa andasse storto, il messaggio
  non può finire a un cliente o al team.

### 9.4 La posta, in sola lettura

Ogni mattina il vault legge la posta ricevuta e inviata e aggiorna i loop aperti dei progetti:
se un cliente ha confermato per email, il loop si chiude da solo, con la email come prova.
Claude **non può inviare**: prepara bozze, che controllo e mando io.

È lo strumento più potente e più delicato. Ti consiglio di accenderlo per ultimo, quando ti
fidi del resto.

| Cosa serve | |
|---|---|
| App | Apple Mail su Mac, con i tuoi account già dentro |
| Costo | Nessun servizio in più, ma il giro giornaliero consuma una parte del tuo abbonamento Claude |
| Cosa dici a Claude | «Attiva la posta in sola lettura» (ti spiega prima cosa fa e cosa costa) |

### 9.5 Tutto il resto che entra nel vault

- **Documenti scaricati** (Word, PDF, Excel): «leggi l'ultimo documento scaricato».
- **Video YouTube e Loom**: «scarica la trascrizione di questo video nel progetto X».
- **Vocali** di WhatsApp o Slack: «trascrivi questo vocale». La trascrizione avviene sul tuo
  computer, il file non va da nessuna parte.
- **Calendario**: può comparire nel cruscotto e nel briefing.

Alcuni di questi chiedono di installare piccoli programmi gratuiti. Claude te lo dice prima e
ti guida.

### 9.6 La mia settimana, in pratica

- **Durante il giorno** lavoro in VS Code con Claude, una chat per argomento. Le call si
  registrano e si smistano da sole. Il cruscotto resta aperto in una finestra.
- **La mattina** apro una sessione e trovo in testa cosa è cambiato: cosa ha scaricato da
  GitHub, cosa ha aggiornato dalla posta, quante cose aspettano in coda.
- **Il venerdì**, quindici minuti di review.
- **Di notte** il vault lavora da solo (capitolo 10).

---

## 10. Farlo lavorare nel cloud (livello 3)

Fin qui tutto vive sul tuo computer. Il livello 3 aggiunge tre cose: una copia di sicurezza
con la storia di ogni modifica, il vault dal telefono, e il lavoro notturno. Si costruiscono
in quest'ordine, e ciascuna funziona senza la successiva.

### 10.1 Il backup su GitHub

GitHub è un servizio che conserva cartelle di file con tutta la loro storia. Per il vault si
usa un **repository privato**: lo vedi solo tu.

Cosa fai tu:

1. Crei un account gratuito su **github.com**.
2. Crei un repository nuovo: nome a piacere, visibilità **Private**, senza aggiungere README
   né altro (deve nascere vuoto).
3. Dici a Claude: **«attiva il backup su GitHub»** e gli incolli l'indirizzo del repository.

Claude prepara il vault, controlla che le chiavi restino fuori, e ti guida nell'unico
passaggio che devi fare tu: il primo invio, in cui GitHub ti chiede di accedere.

Da quel momento a ogni fine sessione il vault si salva da solo. E se un salvataggio fallisce,
lo scopri all'apertura della sessione dopo, non tre settimane più tardi.

**Cosa finisce su GitHub:** tutto, tranne il file delle chiavi e la cartella `_local-only/`.
**Cosa non deve mai essere pubblico:** il repository. Privato, sempre.

Se vuoi solo la storia delle modifiche senza GitHub, esiste anche la via di mezzo: «attiva la
cronologia locale». Puoi tornare indietro nel tempo, ma la copia resta solo sul computer.

### 10.2 Il backup ogni ora

Il salvataggio di fine sessione non parte se chiudi il computer di colpo. Per questo sul mio
Mac un piccolo programma gira ogni ora: scarica le call nuove, le smista, fa il giro posta la
mattina, salva. Dici a Claude: **«attiva il backup orario»**.

Due cose da sapere: funziona solo su Mac, e mentre Claude lavora il kit tiene sveglio il
computer e acceso lo schermo (su un portatile a batteria si sente).

### 10.3 Il vault dal telefono

Con il vault su GitHub puoi lavorarci da qualunque posto, anche a Mac spento:

1. Collega GitHub a Claude: vai su **claude.ai/code**, accedi, scegli di collegare GitHub e
   installa l'app di Claude sul tuo account GitHub dando accesso al repository del vault (per
   i repository privati è obbligatorio).
2. Nell'app Claude sul telefono apri la scheda **Code**, scegli il repository e scrivi.

La sessione gira nel cloud su una copia del vault, e salva su GitHub dopo ogni risposta. Alla
prossima apertura sul Mac, il vault si allinea e ti dice cosa ha scaricato.

Dal telefono non arriva ciò che vive solo sul computer: le chiavi, la posta di Apple Mail, i
Promemoria, il cruscotto.

### 10.4 Il lavoro notturno

Ogni notte una routine nel cloud apre il mio vault e fa il lavoro di manutenzione: smaltisce
venti voci della coda memoria, distilla nel wiki le call arrivate, aggiorna i loop, e mi
lascia in un file solo le cose che richiedono una mia decisione. La mattina trovo il vault più
ordinato di come l'ho lasciato.

Per attivarla: su **claude.ai/code/routines** crei una nuova routine sul repository del vault,
una volta al giorno, e come istruzioni incolli il testo che trovi in
`.claude/routines/digestione-notturna.md`. Oppure lo chiedi a Claude: «aiutami ad attivare la
routine notturna». È la parte più avanzata del sistema: arrivaci dopo qualche settimana di
uso, quando la coda memoria comincia a riempirsi davvero. Le routine sono una funzione recente
di Claude e possono cambiare: se qualcosa non corrisponde, fatti guidare da lui.

### 10.5 Quando scrivono in tanti

Computer, telefono e routine notturna scrivono sullo stesso vault senza vedersi. Le regole che
evitano di perdere dati sono già nel kit:

- ognuno si allinea prima di salvare;
- se due hanno modificato lo stesso file, nessuno script li fonde da solo: Claude li unisce
  nella sessione successiva, tenendo entrambe le versioni, e ti dice cosa ha fatto;
- solo il registro delle azioni si unisce in automatico, perché è un elenco a sola aggiunta.

Tu non devi fare niente: devi solo sapere che se all'apertura Claude ti dice «ho riconciliato
due versioni di questo file», è il sistema che funziona.

---

## 11. Gli errori che ho già pagato io

Ogni regola del sistema esiste perché prima c'è stato un problema. Questi sono quelli che ti
risparmio.

1. **Un backup che fallisce in silenzio non è un backup.** In meno di una settimana 39
   salvataggi sono falliti senza che me ne accorgessi: l'unica traccia era in un file di log
   che nessuno apriva. Ora ogni errore mi viene detto all'apertura della sessione.
2. **Catturare non è ricordare.** Mi sono ritrovato con 121 candidati memoria fermi in coda da
   settimane: tutti catturati, nessuno visibile. La coda va smaltita, non solo riempita.
3. **Fermo era il file, non il progetto.** Il briefing mi dava per bloccata una questione che
   avevo chiuso in call. Da lì l'aggiornamento automatico dei loop, e la regola
   dell'evidenza.
4. **Una spunta non è una chiusura.** Delegato non vuol dire fatto. Si chiude su una prova.
5. **Niente ordini automatici a inizio sessione.** Sapere che la coda ha 40 voci è utile.
   Farsi dirottare ogni sessione a smaltirla no.
6. **Due viste sugli stessi dati finiscono per divergere.** Avevo le task sia in una pagina di
   Obsidian sia nel cruscotto: una era sempre vecchia. Un dato, un posto.
7. **Una fotografia vecchia deve dire di essere vecchia.** Per due giorni il cruscotto mi ha
   mostrato promemoria congelati senza avvisarmi che la fonte non rispondeva.
8. **Citare la fonte con un link, non con il nome scritto.** Sembra un dettaglio: in un
   controllo, 113 file su 226 erano isolati, quasi tutti call che nessuna pagina collegava.
9. **Mai fondere in automatico due versioni dello stesso file.** Si perde contenuto senza
   accorgersene. Gli script si fermano e Claude riconcilia a mano, dicendomi cosa ha unito.
10. **Dipendere dalle porte ufficiali.** Un plugin che leggeva i file interni di un'app ha
    smesso di funzionare al primo aggiornamento. L'API ufficiale è una promessa, i file
    interni no.
11. **Le idee non nascono progetti.** Le cartelle vuote di idee mai partite sporcano tutto.
12. **Quando regola ed esempio litigano, vince l'esempio.** Se Claude sbaglia una cosa
    ricorrente, gli si corregge l'esempio concreto prima di aggiungere l'ennesima regola.

---

## 12. Checklist e domande frequenti

### Checklist

**Livello 1**
- [ ] Abbonamento Claude a pagamento
- [ ] VS Code installato, estensione Claude Code installata, accesso fatto
- [ ] Kit nella cartella Inizio (non Scrivania, non Documenti, non iCloud)
- [ ] Obsidian aperto sulla stessa cartella
- [ ] Export da Claude salvato in `00-inbox/`
- [ ] Primo avvio completato: `me.md` compilato, un progetto per cartella
- [ ] Una settimana di uso quotidiano

**Livello 2** (uno alla volta, solo se ti serve)
- [ ] Call di Granola
- [ ] Cruscotto delle task
- [ ] Briefing
- [ ] Posta in lettura

**Livello 3**
- [ ] Repo GitHub privato e backup
- [ ] Vault dal telefono
- [ ] Routine notturna

### Domande frequenti

**Devo saper programmare?** No. Tutto quello che c'è di tecnico lo fa Claude. Tu gli dici
cosa vuoi.

**I miei dati dove finiscono?** Nei file sul tuo computer. Claude li legge per lavorarci, come
quando gli incolli un testo in chat. Su GitHub vanno solo se attivi il livello 3, in un repo
privato tuo.

**Funziona su Windows?** La struttura, le regole e la memoria sì: sono file di testo. Gli
strumenti dei livelli 2 e 3 (promemoria, posta, cruscotto, automazioni orarie) sono scritti
per Mac e su Windows vanno adattati. Chiedi a Claude di farlo: è un buon primo esercizio.

**Posso cambiare la struttura?** Sì, ed è previsto. Prima chiedi a Claude «perché è fatto
così?»: in `METODO.md` c'è la ragione di ogni scelta. Poi decidi tu, e la decisione si scrive
in `CAPISALDI.md`.

**Uso Notion, non Obsidian.** Il vault sono file: Obsidian è solo un modo comodo di leggerli.
Notion tiene i dati dentro Notion, ed è il motivo per cui non lo uso per questo.

**Quanto costa tenerlo acceso?** La base costa solo l'abbonamento Claude che hai già. Gli
strumenti aggiungono i costi dei servizi che colleghi, se sono a pagamento.

**E se Claude sbaglia qualcosa?** Quasi tutto è reversibile: i file si correggono, e con il
livello 3 ogni modifica ha una storia e si torna indietro. Per questo le azioni che non si
possono annullare passano sempre da te.

**Mi sono perso, da dove riparto?** Apri la chat e scrivi: «leggi GUIDA.md e dimmi a che
punto sono». Lui guarda il vault e ti dice cosa manca.
