# Installazione e configurazione

## Requisiti

- Windows 11 a 64 bit;
- Python CPython 3.11 o successivo, a 64 bit, per l'ambiente di sviluppo;
- middleware ufficiale della smart card o del token;
- DLL PKCS#11 della stessa architettura del processo Python;
- accesso in lettura ai sorgenti e in scrittura alle relative cartelle.

La versione attuale è un ambiente di sviluppo eseguibile. Non è ancora
disponibile un installer autonomo per PC senza Python.

## Preparazione dell'ambiente

Aprire PowerShell nella cartella del progetto ed eseguire:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.lock
.venv\Scripts\python -m pip install -e . --no-deps
```

`requirements.lock` contiene le versioni provate con CPython 3.13 x64. Dopo il
collaudo hardware il file dovrà essere rigenerato e nuovamente verificato.

## Avvio

```powershell
.venv\Scripts\python -m mfirma
```

Oppure fare doppio clic su `avvia_mFirma.cmd`.

## Individuare la DLL e le etichette

Il percorso della DLL dipende dal produttore. Non copiare DLL da altri PC e non
rinominarle: installare il middleware ufficiale e usare la libreria fornita.

Per enumerare dati pubblici senza richiedere il PIN:

```powershell
.venv\Scripts\python -m mfirma.probe "C:\percorso\middleware.dll"
```

L'output JSON contiene, quando il dispositivo lo permette:

- identificativo dello slot;
- etichetta, seriale, produttore e modello del token;
- etichette e ID dei certificati pubblici.

Alcuni dispositivi richiedono il login anche per leggere i certificati. Il
probe non tenta l'autenticazione e in questo caso restituisce un messaggio.

## File di configurazione

La configurazione viene salvata per utente in:

```text
%LOCALAPPDATA%\mFirma\config.json
```

Esempio:

```json
{
  "config_version": 1,
  "monitor": {
    "root": "C:\\Da firmare",
    "recursive_within_person": true,
    "stability_seconds": 5
  },
  "output": {
    "suffix": "_firmato"
  },
  "signature": {
    "preset": "bottom_right",
    "margin_points": 24.0,
    "width_points": 180.0,
    "height_points": 60.0,
    "reason": "",
    "location": ""
  },
  "pkcs11": {
    "module_path": "C:\\Program Files\\Vendor\\token-pkcs11.dll",
    "token_label": "TOKEN",
    "certificate_label": "FIRMA",
    "key_label": ""
  }
}
```

Il PIN non deve essere aggiunto manualmente al file. La scrittura della
configurazione è atomica: prima viene creato un temporaneo e poi sostituito il
file completo.

## Aggiornamento delle dipendenze

Aggiornare le versioni soltanto in un ramo o ambiente di prova. Dopo ogni
aggiornamento eseguire almeno:

```powershell
.venv\Scripts\python -m pytest -p no:cacheprovider
```

Ripetere poi la firma singola, la co-firma e il batch con il token reale.

