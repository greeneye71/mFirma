# Installazione e configurazione

## Requisiti

- Windows 11 a 64 bit;
- Python CPython 3.11 o successivo, a 64 bit, per l'ambiente di sviluppo;
- middleware ufficiale della smart card o del token;
- DLL PKCS#11 della stessa architettura del processo Python;
- accesso in lettura ai sorgenti e in scrittura alle relative cartelle.

La versione attuale include uno script di preparazione e riparazione locale, ma
richiede che Python sia presente sul PC. Non è ancora disponibile un pacchetto
autonomo con installer e disinstallazione Windows per PC senza Python.

## Preparazione dell'ambiente

Fare doppio clic su `avvia_mFirma.cmd`: al primo avvio vengono creati
automaticamente l'ambiente `.venv` e l'installazione locale di mFirma. La prima
preparazione richiede una connessione Internet.

Per installare o riparare l'ambiente senza avviare l'applicazione, fare doppio
clic su `installa_mFirma.cmd`.

Lo script:

1. cerca prima il Python Launcher (`py`) e poi il comando `python`;
2. accetta soltanto Python 3.11 o successivo a 64 bit;
3. crea `.venv` nella cartella del progetto, se non esiste;
4. installa le versioni definite in `requirements.lock`;
5. installa il progetto in modalità modificabile e verifica gli import.

Non copiare `.venv` da un altro PC: contiene percorsi legati alla macchina e
deve essere ricreato localmente.

Se manca Python 3.11+ x64, installare la versione verificata aprendo PowerShell
ed eseguendo:

```powershell
winget install --id Python.Python.3.13 -e
```

Dopo l'installazione chiudere e riaprire il terminale. In alternativa, per
preparare tutto manualmente, aprire PowerShell nella cartella del progetto ed
eseguire:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.lock
.venv\Scripts\python -m pip install -e . --no-deps
```

`requirements.lock` contiene le versioni provate con CPython 3.13 x64. Dopo il
collaudo hardware il file dovrà essere rigenerato e nuovamente verificato.

## Aggiornamento e riparazione

Dopo `git pull`, eseguire nuovamente `installa_mFirma.cmd` se sono cambiati
`requirements.lock` o `pyproject.toml`. Lo script è rieseguibile e aggiorna
l'ambiente esistente senza toccare la configurazione utente o i PDF.

Se l'ambiente è danneggiato e la riparazione non riesce, chiudere mFirma,
rinominare `.venv` in `.venv_old` e rieseguire `installa_mFirma.cmd`. Dopo aver
verificato il funzionamento, la vecchia cartella può essere eliminata.

## Avvio

```powershell
.venv\Scripts\python -m mfirma
```

Oppure fare doppio clic su `avvia_mFirma.cmd`, che crea o ripara l'ambiente
quando Python o uno dei moduli richiesti non sono disponibili.

## Individuare la DLL e le etichette

Il percorso della DLL dipende dal produttore. Non copiare DLL da altri PC e non
rinominarle: installare il middleware ufficiale e usare la libreria fornita.

Nella GUI premere `Rileva…` accanto al percorso della DLL. La ricerca:

1. legge le posizioni dei software installati registrate da Windows;
2. controlla `Program Files`, `LocalAppData` e `System32` con nomi compatibili;
3. scarta file non DLL e architetture diverse da x64;
4. interroga ogni candidata in un processo separato con timeout;
5. mostra soltanto i moduli che rispondono come PKCS#11.

La ricerca non chiede il PIN. Un modulo può essere riconosciuto anche senza un
token collegato; in tal caso non saranno disponibili etichette da compilare.
Non esiste una posizione Windows obbligatoria per i moduli PKCS#11, quindi
`Sfoglia…` rimane disponibile per middleware non rilevati.

Anche una DLL scelta con `Sfoglia…` viene interrogata automaticamente. Se il
token espone un solo certificato pubblico, l'etichetta viene compilata. In
presenza di più certificati viene preferito automaticamente l'unico con uso
X.509 `contentCommitment`; se la scelta resta ambigua, mFirma mostra una finestra
con etichette e uso rilevato. Il PIN non viene richiesto in questa fase.

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
