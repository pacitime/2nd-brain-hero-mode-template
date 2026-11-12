# _local-only: ciò che non lascia mai questo computer

Questa cartella è esclusa da Git: non finisce su GitHub, nemmeno per sbaglio. E Claude non
può leggerla in chat: un hook lo blocca.

- `secrets/`: le chiavi degli strumenti collegati, nel file `.env`. Parti da `.env.example`:
  copialo, rinominalo `.env`, e incolla le chiavi **tu, a mano**, nel file. Non incollarle mai
  nella chat.
- `calls/`: le call con dati di salute, che il router mette qui da solo.

Per un singolo file troppo delicato per stare su GitHub (un documento d'identità che ti serve
a portata di mano, un contratto riservato), mettilo qui.

**Attenzione:** ciò che sta qui non è nel backup su GitHub. Se ti serve una copia di
sicurezza, pensaci tu (un disco esterno, il backup del computer).
