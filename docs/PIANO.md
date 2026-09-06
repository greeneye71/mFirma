# Piano di progetto

## Scelta iniziale

L'MVP implementa un solo percorso completo: **PAdES Baseline B-B visibile via
PKCS#11**, con firma seriale di più file e output affiancato al sorgente. Questa
scelta consente sia il batch sia firme successive sullo stesso PDF, preservate
da aggiornamenti incrementali. Non include TSA e non pretende di determinare lo
status qualificato del certificato.

La GUI iniziale 0.1.0 usava Tkinter. È stata sostituita da **PySide6 con
PySide6-Fluent-Widgets** per tray, anteprima PDF interattiva, navigazione Fluent
e tabelle model/view. La specifica operativa è in
[SPECIFICA_INTERFACCIA.md](SPECIFICA_INTERFACCIA.md).

## Fasi

### Evoluzioni concordate: non implementate

- Modalità Automatica: esecuzione silenziosa nell'area di notifica e monitoraggio
  di una cartella con coppie `documento.pdf` / `documento.json`. Formato JSON,
  comandi, condizioni di avvio, gestione del PIN, duplicati ed esiti saranno
  definiti successivamente. Nessun monitor o comando automatico è attivo.
- Database esterno: raccolta delle registrazioni da più postazioni, con invio
  differito quando la rete torna disponibile e deduplicazione per operation_id.
  È implementato soltanto il [registro locale](REGISTRO_FIRME.md).

### 1. Nucleo eseguibile (questa consegna)

- modelli indipendenti dalla GUI;
- scanner, esclusioni e conteggi per persona;
- preset di firma consapevoli della rotazione pagina;
- naming, file temporaneo e pubblicazione senza sovrascrittura;
- provider PKCS#11 isolato e sessione batch;
- firma PAdES B-B e verifica immediata;
- GUI per configurare, selezionare e firmare più file;
- bootstrap Windows per creare e riparare automaticamente `.venv`;
- rilevamento assistito dei moduli PKCS#11 x64, lettura Key Usage e scelta del
  certificato con probe fuori processo;
- test automatici con provider fittizio confinato ai test.
- aspetto firma vettoriale completo/compatto con font incorporato, metadati
  leggibili e importazione pubblica `StaticStampStyle`.

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

- infrastruttura PySide6/Fluent, modello tabellare, dashboard filtrabile e
  scanner Qt: **implementati nell'avvio predefinito**;
- impostazioni, persistenza, discovery Qt e scelta del certificato pubblico:
  **implementati e testati senza hardware**;
- anteprima `QPdfDocument/QPdfView`, overlay condiviso, zoom, preset,
  trascinamento e ridimensionamento: **implementati e testati**;
- dialogo PIN effimero, worker del `BatchOrchestrator`, avanzamento reale,
  annullamento ed esito: **implementati e testati senza hardware**;
- applicazione al PDF firmato del posizionamento scelto nell'anteprima:
  **implementata e verificata con firma software di test**;
- icona tray, chiusura ordinata, avvio Qt predefinito e rimozione della GUI
  Tkinter: **implementati e coperti da test offscreen**;
- persistenza sicura di dimensione/posizione finestra e rifinitura
  accessibilità/tastiera: **implementate e testate automaticamente**;
- tema chiaro/scuro e scaling: **smoke test offscreen**, resta il collaudo
  visivo sulle postazioni Windows reali;
- selezione esplicita del token quando più dispositivi sono collegati, con
  seriale pubblico e inventario certificati per dispositivo: **implementata e
  testata senza hardware**;
- istanza singola, launcher leggero, IPC per utente, import asincrono e verbo
  classico di Esplora file: **implementati e testati automaticamente**; resta il
  collaudo manuale con 1, 50 e 100 selezioni su Windows 11;
- cronologia locale degli ultimi 100 batch reali, con dettaglio ricostruibile e
  persistenza atomica fuori dal thread GUI: **implementata e testata**;
- log rotanti con accesso dal riepilogo: **implementati**;
- prossimo incremento: destinazione separata con conservazione dell'albero
  relativo, da chiudere come confine verticale prima del packaging.

### 4. Pilot

- destinazione separata preservando l'albero relativo;
- pacchetto PyInstaller one-folder e installer Windows per utente, autonomi da
  Python;
- prove su share con 1.000 PDF, rete interrotta e copie lente;
- test su PC pulito con antivirus e policy aziendali;
- manuale breve e release pilota.
- opzionale, al termine: valutare la normalizzazione su copia temporanea dei PDF
  con riferimenti ibridi, soltanto senza firme preesistenti e con confronto del
  contenuto prima/dopo; non disabilitare semplicemente i controlli rigorosi.

## Rischi e decisioni aperte

| Tema | Decisione attuale | Verifica necessaria |
|---|---|---|
| Token | PKCS#11 x64 | DLL, slot, certificato e algoritmi reali |
| PIN | richiesto una volta dall'app per il batch | il middleware può richiederlo ancora |
| Profilo | PAdES B-B, SHA-256, senza TSA | requisiti legali/aziendali |
| Co-firma | nuovo campo incrementale | PDF reali e firme/certificazioni pregresse |
| Output | stessa cartella, `_firmato` | permessi sulla share e politica definitiva |
| UI | migrazione a PySide6 + PySide6-Fluent-Widgets | accessibilità, scaling, packaging e resa su postazioni reali |
| Explorer | verbo classico per utente; menu moderno rinviato | prova reale con 1, 50 e 100 percorsi |

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
