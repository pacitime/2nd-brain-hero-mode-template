# team-roster: fonte unica di membri e liste (condivisa tra skill)

> Riferimento condiviso da `clickup-task-template` e `task-sync`, per non copiare la stessa mappa
> in più skill. **Fonte di verità = ClickUp**: per i nomi non elencati usa
> `clickup_find_member_by_name` / `clickup_resolve_assignees`, o chiedi.

> **Modello vuoto: va compilato.** Finché restano i segnaposto `<…>`, le skill non hanno id da
> usare: li cercano ogni volta su ClickUp e chiedono conferma.
> Per compilarlo chiedi a Claude: «leggi i miei workspace ClickUp e compila il team-roster».
> Claude legge membri e gerarchia (`clickup_get_workspace_members`,
> `clickup_get_workspace_hierarchy`, sola lettura), ti mostra la proposta e scrive qui solo dopo
> il tuo ok.

## Utente / assegnatario di default
<Nome Cognome> `<id utente>`

## Membri → id (per assegnazione/delega)
- <Nome Cognome> `<id>`
- <Nome Cognome> `<id>`
- <Nome Cognome> `<id>`

## Progetto → workspace → lista di default
> La lista si **propone** in base al progetto ma si **conferma sempre** (mai sceglierla in silenzio).
> Scrivi il percorso completo: workspace · space › folder › lista.

- **<progetto o area>** → workspace <Nome workspace> `<id workspace>` · space <Nome space> `<id>`
  → folder <Nome folder> `<id>` → lista **`<Nome lista> <id lista>`** ← **default**
  (casi particolari: <tipo di task> → `<Nome lista> <id lista>`)
- **<progetto o area>** → workspace <Nome workspace> `<id workspace>` · lista `<Nome lista> <id lista>`
  (da non usare: `<Nome lista> <id lista>`, <perché no, per esempio «lista privata, il team non la vede»>)

> ⚠️ **Trappola da ricordare: il nome della lista non basta.** Due liste possono chiamarsi allo
> stesso modo e vivere sotto cartelle (quindi progetti) diverse. Prima di creare una task si
> guarda sotto quale **folder** vive la lista: nel dubbio `clickup_get_workspace_hierarchy`
> **prima** di proporre, e nella proposta si scrive il percorso completo, non solo il nome.
