# Automazioni: cronologia, backup su GitHub, giro orario

> **Per Claude.** Queste sono istruzioni da eseguire quando l'utente lo chiede («attiva il backup
> su GitHub», «attiva il backup orario», «spegni il giro orario», «perché il backup non va?»).
> Niente di ciò che sta qui è acceso da solo, e niente è obbligatorio: il vault funziona anche
> senza. Regole per te mentre le esegui:
>
> - **un passo alla volta**, dicendo all'utente cosa stai per fare e perché, in parole semplici;
> - **mai `sudo`**, mai `git push --force`, mai cancellazioni di massa;
> - i comandi che toccano il sistema (`git commit`, `git push`, `launchctl`) chiedono conferma
>   all'utente: è voluto, non aggirarlo;
> - gli strumenti di scrittura non possono scrivere fuori dalla cartella del vault (lo blocca
>   `block-secrets.py`): per mettere un file in `~/Library/LaunchAgents/` si usa `cp` da shell;
> - **solo macOS** per tutto ciò che riguarda `launchd` (sezioni 4 e 5). Git e GitHub (sezioni 2
>   e 3) funzionano ovunque.

## 1. Cosa c'è, e cosa è già acceso

| Pezzo | Cosa fa | Quando parte |
|---|---|---|
| `auto-backup.sh` | Salva il vault: commit git e, se c'è GitHub, push | A fine sessione (hook `SessionEnd`), già acceso. Ogni ora solo se lo attivi (sezione 4) |
| `cloud-sync.sh` | Salva su GitHub il lavoro fatto da telefono o browser | Dopo ogni risposta, ma solo nelle sessioni cloud. Sul computer non fa nulla |
| `autopilot.py` | Giro orario: call nuove, smistamento, giro posta, backup | Solo se lo attivi (sezione 4) |
| `health_check.py` | Controlla che tutto ciò che sembra acceso lo sia davvero | A comando: `python3 .claude/scripts/health_check.py` |
| `session-start-context.py` | All'apertura allinea il vault con GitHub e dice cosa ha scaricato | A ogni sessione, già acceso |
| `project-context.py` | Quando un messaggio nomina un progetto (gli `alias` in `brain.json`), carica una volta per sessione metodo, essenziali, titoli dei loop aperti e skill del progetto | A ogni messaggio, già acceso. Tace se nessun progetto è nominato |

Il salvataggio ha tre livelli. Ogni script fa solo ciò che il livello permette, e ai livelli
bassi tace:

| Livello | Com'è il vault | Cosa succede a fine sessione |
|---|---|---|
| Base | Una cartella normale, senza git | Niente. Nessun errore, nessun log |
| Cronologia locale | Repository git, senza remote | Commit locale: puoi tornare indietro, ma una copia fuori dal computer non c'è |
| GitHub | Repository git con remote `origin` | Commit, allineamento col remoto, push sul ramo `main` |

Per sapere a che livello è il vault: esiste la cartella `.git`? (`ls -d .git`). Se sì,
`git remote -v` dice se c'è `origin`.

## 2. «Attiva la cronologia locale» (git senza GitHub)

1. Controlla che git ci sia **senza lanciarlo**: `xcode-select -p`. Se risponde con un percorso,
   git c'è. Se dà errore, mancano gli strumenti da riga di comando di macOS: chiedi all'utente
   se vuole installarli (`xcode-select --install` apre una finestra di macOS, lui clicca
   «Installa» e aspetta qualche minuto). Non proseguire finché `git --version` non risponde.
2. Dalla radice del vault: `git init -b main`. Il ramo **deve** chiamarsi `main`: tutti gli
   script lo danno per scontato. Se il repository esiste già con un altro nome di ramo:
   `git branch -M main`.
3. Git deve sapere chi firma i salvataggi. Chiedi all'utente nome ed email, poi (valgono solo
   per questo repository): `git config user.name "Nome Cognome"` e
   `git config user.email "indirizzo"`. Senza questi due valori il commit fallisce e
   `backup.log` lo scrive.
4. Leggi `.gitignore` (con lo strumento di lettura) e verifica che contenga `.env`, `*.env`,
   `_local-only/` e `.claude/data/*`. Se manca una riga, aggiungila **prima** del primo commit.
5. Primo salvataggio: `git add -A`, poi guarda `git status --short` e controlla a occhio che
   nell'elenco non ci siano file di chiavi o cartelle che dovevano restare fuori. Poi
   `git commit -m "primo salvataggio"`.

Da qui in poi `auto-backup.sh` fa un commit a ogni fine sessione. In `.claude/data/backup.log`
comparirà la riga `commit locale OK, nessun remote 'origin': niente push`: è normale.

## 3. «Attiva il backup su GitHub»

Serve: un account GitHub (gratuito) e il livello «cronologia locale» già fatto (sezione 2).

1. **Il repository deve essere PRIVATO.** Il vault contiene la vita e il lavoro dell'utente.
   L'utente lo crea su github.com (New repository, visibilità Private, **senza** README, senza
   .gitignore, senza licenza: deve nascere vuoto) e ti incolla l'indirizzo.
2. `git remote add origin <indirizzo>`.
3. **Il primo push lo lancia l'utente** nel terminale di VS Code, perché GitHub gli chiede di
   autenticarsi: `git push -u origin main`. Se sul computer c'è il comando `gh`, la strada più
   semplice è `gh auth login` seguito da `gh auth setup-git` (sempre lanciati da lui). Lo scopo
   è che la credenziale resti salvata nel Portachiavi: i salvataggi automatici girano senza
   nessuno davanti e non possono rispondere a una richiesta di password. *(Da verificare sulla
   macchina dell'utente: il flusso di accesso di GitHub cambia nel tempo.)*
4. Verifica: `git status -sb` deve mostrare `## main...origin/main` senza «ahead», e
   `python3 .claude/scripts/health_check.py` deve dare `push: allineato con origin`.
5. In `.claude/config/brain.json` il campo `git_author` può restare vuoto: `health_check.py`
   usa il nome di `git config user.name`. Va riempito solo se i commit del computer devono
   essere riconosciuti con un nome diverso da quello.

Da qui in poi: a fine sessione il vault parte per GitHub; all'apertura si allinea e lo dice.
Se `auto-backup.sh` trova il remoto ancora vuoto fa da solo il primo push; se il ramo corrente
non è `main` non spinge nulla e lo scrive nel log.

## 4. «Attiva il backup orario» (launchd, solo Mac)

A cosa serve: il backup di fine sessione non parte se la sessione non viene chiusa bene, o se
i file li cambia un altro programma (Obsidian, il cruscotto). Il giro orario copre quei buchi.
Ha senso **solo dal livello GitHub o cronologia locale**: senza git non ha nulla da salvare.

### 4.1 Quale dei due modelli

In `.claude/scripts/` ci sono due modelli. **Se ne installa uno solo, mai tutti e due.**

| Modello | Cosa lancia ogni ora | Quando sceglierlo |
|---|---|---|
| `com.secondbrain.autopilot.plist` | `autopilot.py` con Python: call nuove, smistamento, giro posta, backup. I moduli non configurati si saltano da soli | **Scelta normale.** Obbligata se il vault sta in Scrivania, Documenti, Download o iCloud Drive (vedi trappola 3) |
| `com.secondbrain.vault-backup.plist` | Solo `auto-backup.sh` con `/bin/bash` | Solo se l'utente vuole il backup e nient'altro, **e** il vault sta fuori dalle cartelle protette |

Prima di installare `autopilot`, di' all'utente cosa farà oltre al backup: se ha configurato le
call o la posta, ogni ora (la posta una volta al giorno) quei moduli gireranno da soli.

### 4.2 Riempire i segnaposto

I modelli contengono tre segnaposto. **Non si installano così come sono.**

| Segnaposto | Valore | Come trovarlo |
|---|---|---|
| `__VAULT__` | Percorso assoluto del vault, senza barra finale | `pwd` dalla radice del vault |
| `__HOME__` | Cartella dell'utente | `cd ~ && pwd` |
| `__PYTHON__` | Un interprete `python3` vero, con percorso assoluto (solo per `autopilot`) | Vedi sotto |

Scelta di `__PYTHON__`, in quest'ordine:

1. Se c'è Homebrew (`command -v brew`): `<prefisso>/opt/python@3/libexec/bin/python3`, dove
   `<prefisso>` è l'uscita di `brew --prefix`. Usa questo solo se il file esiste (`ls -l`).
   È il percorso che resiste agli aggiornamenti. **Non** usare `<prefisso>/bin/python3`: un
   aggiornamento di Python lo può togliere, e il giro si ferma senza dire nulla.
2. Altrimenti `/usr/bin/python3`, ma solo se `xcode-select -p` risponde con un percorso.
3. In ogni caso prova il candidato prima di usarlo: `<percorso> --version` deve rispondere
   con una versione 3.9 o successiva.

Poi crea la copia compilata **dentro il vault**, in una cartella fuori da git:

1. `mkdir -p .claude/data/launchd`
2. Leggi il modello e scrivi `.claude/data/launchd/<nome del modello>` con lo strumento di
   scrittura, sostituendo ogni segnaposto (anche quelli nel commento in testa). Se un percorso
   contiene `&` scrivilo come `&amp;` (è un file XML). Gli spazi vanno bene così.
3. Controlla: nel file non deve restare nessun `__` (cercalo), e
   `plutil -lint .claude/data/launchd/<nome del modello>` deve rispondere `OK`.

### 4.3 Installare

```
mkdir -p ~/Library/LaunchAgents ~/Library/Logs
cp .claude/data/launchd/com.secondbrain.autopilot.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.secondbrain.autopilot.plist
```

Il giro parte subito una prima volta (`RunAtLoad`) e poi ogni ora. Verifica dopo un minuto:

- `.claude/data/autopilot.log` ha le righe del giro (`granola: ...`, `router: ...`,
  `backup: exit 0`). Con il modello `vault-backup` si guarda invece `.claude/data/backup.log`;
- `~/Library/Logs/secondbrain-autopilot.log` è vuoto, o comunque senza `Operation not
  permitted` e senza errori di Python;
- `python3 .claude/scripts/health_check.py` mostra `giro orario: ultimo giro 0.0h fa`.

Se macOS mostra una finestra del tipo «python3 vorrebbe accedere ai file nella cartella ...»,
l'utente deve rispondere **Consenti**.

### 4.4 Disinstallare

```
launchctl bootout gui/$(id -u)/com.secondbrain.autopilot
rm ~/Library/LaunchAgents/com.secondbrain.autopilot.plist
```

(Con l'altro modello l'etichetta è `com.secondbrain.vault-backup`.) Il backup di fine sessione
resta attivo: quello è un hook, non dipende da launchd.

### 4.5 Aggiornare (vault spostato, Python cambiato, modello modificato)

Disinstalla (4.4), rifai la copia compilata (4.2), reinstalla (4.3). Non c'è una scorciatoia:
vedi trappola 1.

## 5. Le trappole di macOS

1. **launchd ignora i collegamenti.** In `~/Library/LaunchAgents/` deve esserci una **copia
   vera** del plist, non un link simbolico. Conseguenza: se cambi il file nel vault, quello
   installato **non** si aggiorna. Va ricopiato, e il job va scaricato e ricaricato (4.5).
2. **Un aggiornamento di Python può spegnere il giro in silenzio.** Il plist punta a un
   interprete preciso; se un aggiornamento (Homebrew) toglie quel percorso, launchd non trova
   più il programma e il giro smette, senza nessun messaggio. `health_check.py` lo vede dal
   sintomo: `giro orario: fermo da Nh`, con la nota `L'interprete del plist non esiste più`.
   Rimedio: 4.5 con il percorso nuovo. Per i programmi che restano sempre accesi (il cruscotto)
   vale una variante: dopo l'aggiornamento il processo resta su con l'interprete vecchio, i
   moduli non ancora caricati falliscono e macOS gli nega i file del vault; va riavviato subito.
3. **Scrivania, Documenti, Download e iCloud Drive sono cartelle protette.** Un job di launchd
   che parte con `/bin/bash` e tocca un vault lì dentro riceve `Operation not permitted`. È il
   motivo per cui il backup gira prima di tutto da un hook di sessione, e per cui il giro orario
   parte da Python (i programmi che lancia, git e bash, ereditano il suo permesso). La soluzione
   più semplice resta tenere il vault fuori da quelle cartelle, per esempio nella cartella
   Inizio. Se il vault è lì e il log mostra `Operation not permitted` anche con `autopilot`:
   Impostazioni di Sistema, Privacy e sicurezza, «File e cartelle» (o «Accesso completo al
   disco») e si abilita l'interprete indicato nel plist. *(Da verificare su una macchina
   pulita: dove questo sistema è nato il permesso era già stato dato.)*
4. **I log di launchd stanno fuori dal vault** (`~/Library/Logs/`), apposta. Sono file che apre
   launchd, non lo script. Dove questo sistema è nato, il job che teneva i log dentro un vault
   in una cartella protetta non partiva, e quelli con i log fuori funzionano. *(Prudenza, non
   certezza: la causa esatta non è stata isolata.)* Non spostarli nel vault.
5. **launchd parte con un PATH minimo.** `auto-backup.sh` aggiunge da sé le cartelle di
   Homebrew per trovare `git`. Uno script nuovo lanciato da launchd deve fare lo stesso, o usare
   percorsi assoluti.
6. **Nessuno risponde alle domande.** Un job in background non può digitare una password né
   cliccare una finestra. Il push funziona solo se la credenziale di GitHub è già salvata
   (sezione 3, passo 3). Il sintomo è `commit OK ma push FALLITO` in `backup.log`. Lo stesso
   vale per i permessi di Automazione (Posta, Promemoria) e di Accessibilità (gestire le
   finestre di altre app), che macOS non concede in anticipo: la prima volta il passo va fatto
   girare a mano, con l'utente davanti allo schermo, così la richiesta compare e lui la approva.
7. **Mac addormentato, giro fermo.** Con il Mac in stop launchd non lancia nulla, e i giri
   saltati non vengono recuperati: si riparte dal primo intervallo dopo il risveglio. Per questo
   `health_check.py` suona solo oltre le 26 ore, e il backup di fine sessione resta comunque.
8. **`git` su un Mac senza strumenti da riga di comando apre una finestra di installazione.**
   Per questo gli script guardano se esiste la cartella `.git` prima di chiamare git. Se
   scrivi uno script nuovo, fai lo stesso.

## 6. Più scrittori sullo stesso repository

Dal livello GitHub in poi sul vault possono scrivere in tre: **il computer** (`auto-backup.sh`,
a fine sessione e ogni ora), **una routine notturna in cloud** e **una sessione dal telefono**
(`cloud-sync.sh`, dopo ogni risposta). Non si vedono fra loro. Le regole, che gli script
rispettano già e che valgono anche per te:

- **Ci si allinea prima di pubblicare.** `auto-backup.sh` fa `fetch` e `rebase` prima del
  `push`. Senza, appena un altro scrittore ha pubblicato per primo il push viene rifiutato, a
  ogni giro, e l'unica traccia resta in un log che nessuno legge.
- **L'apertura di sessione allinea il vault** (solo in avanti, `merge --ff-only`) **e lo dice**:
  una sessione parte sempre sopra il lavoro degli altri.
- **Se le storie divergono, gli script non fondono da soli.** Una fusione automatica su file che
  due lati hanno riscritto perde contenuto in silenzio: per una memoria è il guasto peggiore.
  `auto-backup.sh` annulla il rebase e lo scrive nel log; `cloud-sync.sh` mette il lavoro al
  sicuro su un ramo `cloud/da-riconciliare-...`; l'apertura di sessione avvisa.
- **La riconciliazione la fai tu, in sessione, appena compare l'avviso** (CLAUDE.md, sezione 10):
  1. `git fetch origin main`, poi guarda i due lati: `git log --oneline HEAD..origin/main` e
     `git log --oneline origin/main..HEAD`;
  2. `git merge origin/main` (per un ramo cloud: `git merge origin/cloud/da-riconciliare-...`).
     Mai `-X ours`, mai `-X theirs`, mai `push --force`;
  3. per ogni file in conflitto tieni **entrambi i lati**: è una fusione di significato, pezzo
     per pezzo, non la scelta di una versione. Rileggi il risultato;
  4. `git add`, `git commit`, una riga in `audit-log.md` che dice cosa hai fuso, `git push
     origin main`;
  5. di' all'utente cosa è stato fuso. Non gli si chiede se farlo. Gli si portano solo le
     **contraddizioni vere** fra i due lati (due decisioni opposte sulla stessa cosa): quelle
     non le risolvi tu.
  Tutto è reversibile con git.
- **Unica eccezione: `audit-log.md`.** In `.gitattributes` ha `merge=union`: è un registro a
  sola aggiunta su cui scrivono tutti, e per un registro «tieni tutte le righe» è la soluzione
  giusta per definizione. **Non estenderlo ad altri file.**
- **Non arriva in cloud ciò che vive solo sul computer:** i file `.env`, la cartella
  `_local-only/`, la memoria locale di Claude Code, le app del Mac (Posta, Promemoria).

**Invariante: un backup fallito non deve poter restare invisibile.** Un log che nessuno legge
non è un allarme. Gli allarmi veri sono l'apertura di sessione e `health_check.py`.

## 7. «Perché il backup non va?»

Guarda, in quest'ordine:

1. `python3 .claude/scripts/health_check.py`: le righe `push`, `backup`, `giro orario`.
2. `.claude/data/backup.log`, ultime righe. I messaggi dicono già la causa:

| Riga nel log | Significa | Cosa fare |
|---|---|---|
| (il file non esiste) | Il vault non è un repository git | Sezione 2, se l'utente vuole il backup |
| `nessuna modifica: skip` | Niente da salvare | Niente |
| `nessun remote 'origin'` | Livello cronologia locale | Sezione 3, se vuole GitHub |
| `commit FALLITO` | Mancano nome o email di git | Sezione 2, passo 3 |
| `il ramo corrente e' '...', non 'main'` | Si sta lavorando su un altro ramo | Tornare su `main`, o `git branch -M main` |
| `fetch FALLITO` | Rete assente o accesso a GitHub scaduto | Riprova da solo; se dura, sezione 3 passo 3 |
| `CONFLITTO col remoto` | Storie divergenti | Sezione 6, riconciliazione |
| `push FALLITO` | Accesso a GitHub o rete | Sezione 3, passo 3 |

3. `.claude/data/autopilot.log` e `~/Library/Logs/secondbrain-autopilot.log` (o
   `secondbrain-backup.log`) se il problema è il giro orario: trappole 2 e 3.
4. `launchctl print gui/$(id -u)/com.secondbrain.autopilot` dice se il job è caricato e con
   che esito è uscito l'ultima volta.
