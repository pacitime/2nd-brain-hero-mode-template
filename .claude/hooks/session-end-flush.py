# 2nd Brain Hero Mode · Copyright (c) 2026 Alessandro Pacifico (Pacibrand).
# Vedi LICENZA.md nella radice del vault.
"""Hook SessionEnd: a fine sessione fa partire in sottofondo il salvataggio della
memoria (`memory_flush.py`) ed esce subito.

Non stampa nulla ed esce sempre con 0: un salvataggio che non parte non deve mai
bloccare la chiusura della sessione. La libreria `shared` si cerca nella cartella
`scripts` accanto alla cartella di questo hook, non nel vault indicato dall'ambiente.
"""

import json
import os
import sys

ETICHETTA = "session_end"


def _carica_libreria():
    """Importa `shared` da `../scripts` rispetto a questo file; None se non si carica."""
    cartella_hook = os.path.dirname(os.path.abspath(__file__))
    cartella_script = os.path.join(os.path.dirname(cartella_hook), "scripts")
    if cartella_script not in sys.path:
        sys.path.insert(0, cartella_script)
    try:
        import shared
    except Exception:
        return None
    return shared


def _campo(dati, nome):
    valore = dati.get(nome)
    return "" if valore is None else str(valore)


def main():
    shared = _carica_libreria()
    if shared is None:
        return 0
    try:
        # Freno alla ricorsione: dentro un Claude di servizio non si riparte.
        if shared.invoked_by_flush():
            return 0
        grezzo = sys.stdin.read()
        try:
            dati = json.loads(grezzo) if grezzo.strip() else {}
        except ValueError:
            dati = {}
        if not isinstance(dati, dict):
            return 0
        shared.launch_flush(
            trigger=ETICHETTA,
            transcript_path=_campo(dati, "transcript_path"),
            session_id=_campo(dati, "session_id"),
        )
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
