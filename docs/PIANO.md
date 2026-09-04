# Piano di progetto

## Scelta iniziale

L'MVP implementa un solo percorso completo: **PAdES Baseline B-B visibile via
PKCS#11**, con firma seriale di più file e output affiancato al sorgente. Questa
scelta consente sia il batch sia firme successive sullo stesso PDF, preservate
da aggiornamenti incrementali. Non include TSA e non pretende di determinare lo
status qualificato del certificato.

La GUI usa Tkinter, incluso in Python, per mantenere ridotti dipendenze e
pacchetto. La decisione può essere rivista se i test di usabilità richiederanno
tray, anteprima PDF avanzata o tabelle molto grandi.

## Fasi

### 1. Nucleo eseguibile (questa consegna)

- modelli indipendenti dalla GUI;
- scanner, esclusioni e conteggi per persona;
- preset di firma consapevoli della rotazione pagina;
- naming, file temporaneo e pubblicazione senza sovrascrittura;
- provider PKCS#11 isolato e sessione batch;
- firma PAdES B-B e verifica immediata;
- GUI per configurare, selezionare e firmare più file;
- test automatici con provider fittizio confinato ai test.

### 2. Collaudo hardware (quando saranno disponibili token e PDF)

- registrare modello, firmware, middleware, DLL e architettura;
- eseguire il probe senza PIN;
- firmare un PDF anonimo e validarlo anche con il visualizzatore concordato;
- provare 1, 10 e poi 100 documenti, annotando quante richieste PIN compaiono;
- provare PDF ruotati, già firmati, cifrati e anomali;
- verificare rimozione token, PIN annullato e un solo tentativo di PIN errato.

Uscita: matrice hardware aggiornata e almeno una combinazione dichiarata
supportata. Fino ad allora PKCS#11 resta `da verificare sul dispositivo reale`.

### 3. Esperienza Windows

- icona tray e avvio per utente;
- anteprima della pagina con rettangolo spostabile;
- enumerazione e scelta certificato nella GUI;
- istanza singola, launcher e selezione multipla da Esplora file;
- log rotanti e cronologia locale.

### 4. Pilot

- destinazione separata preservando l'albero relativo;
- pacchetto PyInstaller one-folder e installer per utente;
- prove su share con 1.000 PDF, rete interrotta e copie lente;
- test su PC pulito con antivirus e policy aziendali;
- manuale breve e release pilota.

## Rischi e decisioni aperte

| Tema | Decisione attuale | Verifica necessaria |
|---|---|---|
| Token | PKCS#11 x64 | DLL, slot, certificato e algoritmi reali |
| PIN | richiesto una volta dall'app per il batch | il middleware può richiederlo ancora |
| Profilo | PAdES B-B, SHA-256, senza TSA | requisiti legali/aziendali |
| Co-firma | nuovo campo incrementale | PDF reali e firme/certificazioni pregresse |
| Output | stessa cartella, `_firmato` | permessi sulla share e politica definitiva |
| UI | Tkinter | accessibilità e resa su postazioni reali |
| Explorer | escluso dalla prima consegna | prova con 1, 50 e 100 percorsi |

## Tracciabilità essenziale

| Requisiti | Moduli | Test/validazione |
|---|---|---|
| FR-MON-001..010 | `scanner.py` | `test_scanner.py`, poi share reale |
| FR-QUE-001..006 | `app.py`, `batch.py` | `test_batch.py` |
| FR-PIN-001..007 | `app.py`, `provider.py` | ispezione config/log e test token |
| FR-PDF-001..012 | `pdf_service.py`, `placement.py` | unit test + PDF e token reali |
| FR-OUT-001..010 | `output.py` | `test_output.py` |
| FR-BAT-001..007 | `batch.py`, `app.py` | `test_batch.py`, batch reali |
| AC-011..017 | integrazione PKCS#11/PDF | obbligatoriamente manuale con hardware |

