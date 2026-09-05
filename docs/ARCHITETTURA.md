# Architettura

> PySide6/Fluent è l'unica interfaccia e viene avviata da `python -m mfirma`.
> La specifica è in [SPECIFICA_INTERFACCIA.md](SPECIFICA_INTERFACCIA.md).

## Obiettivi

L'architettura mantiene separati interfaccia, scansione, orchestrazione, PDF,
output e dispositivo crittografico. Il codice specifico PKCS#11 non è presente
nei componenti che gestiscono cartelle o finestre.

## Flusso principale

```text
Cartella / scelta file
        │
        v
     Scanner ──────> DocumentCandidate
                          │
                          v
     GUI Qt ───────> BatchOrchestrator
                          │  una sessione, job seriali
               ┌──────────┴──────────┐
               v                     v
      PKCS#11 Provider         Output Service
               │                     │
               v                     v
       PDF Service ──────> temporaneo verificato
                                      │
                                      v
                            *_firmato.pdf
```

## Moduli

| Modulo | Responsabilità |
|---|---|
| `scanner.py` | Ricerca PDF, associazione alla persona, esclusioni e stabilità |
| `models.py` | Oggetti di dominio e stati dei job |
| `batch.py` | Deduplicazione, firma seriale, annullamento ed esiti indipendenti |
| `provider.py` | Apertura e chiusura della sessione PKCS#11 |
| `pdf_service.py` | Campo visibile, PAdES B-B e verifica della nuova firma |
| `appearance.py` | Modello e rendering vettoriale dell'aspetto, indipendente dalla GUI |
| `ui/models/` | Modelli Qt per documenti, middleware e certificati |
| `ui/workers/` | Scanner, discovery, anteprima e batch di firma fuori dal thread grafico |
| `ui/pages/` | Dashboard, impostazioni, anteprima, avanzamento, esito e cronologia non simulata |
| `ui/dialogs/` | Scelta di middleware/certificato e acquisizione effimera del PIN |
| `ui/main_window.py` | `MSFluentWindow`, navigazione, tray e coordinamento Qt |
| `ui/tray.py` | Menu tray, ripristino finestra e richiesta di uscita |
| `ui/window_state.py` | Stato geometrico atomico e ripristino entro i monitor disponibili |
| `placement.py` | Coordinate dei quattro preset e trasformazione per rotazione |
| `output.py` | Nome, file temporaneo e pubblicazione senza sovrascrittura |
| `config.py` | Validazione e persistenza atomica della configurazione non segreta |
| `logging_setup.py` | Log UTF-8 rotante, percorso locale e gestione degli handler |
| `probe.py` | Enumerazione pubblica di token e certificati senza PIN |
| `discovery.py` | Ricerca, filtro PE x64 e probe isolato dei moduli PKCS#11 |

## Avvio e ambiente locale

`avvia_mFirma.cmd` è il punto di ingresso per l'utente. Prima dell'avvio
controlla l'esistenza dell'interprete virtuale e prova a importare mFirma e le
dipendenze principali. Se il controllo fallisce richiama
`installa_mFirma.cmd`, che crea o ripara `.venv` usando `requirements.lock` e
installa il progetto in modalità modificabile.

Questo bootstrap resta esterno al codice applicativo e non è un installer
Windows autonomo: Python deve essere già installato sul PC. Configurazione e PDF
sono esterni a `.venv`, quindi la ricostruzione dell'ambiente non li modifica.

## Rilevamento del middleware

La GUI avvia `discovery.py` in un worker. Il modulo raccoglie percorsi candidati
dal registro dei software installati e da un insieme limitato di cartelle
standard, filtrando i nomi tipici di moduli PKCS#11. Prima del caricamento legge
l'intestazione PE e accetta soltanto DLL x64.

Ogni candidata viene passata a `mfirma.probe` in un processo separato, senza
PIN e con timeout. Questo confina blocchi o crash del middleware fuori dal
processo grafico. Il risultato ritorna alla GUI tramite segnali Qt; il percorso
viene salvato soltanto dopo la scelta dell'utente.

Lo stesso probe isolato viene eseguito su una DLL scelta manualmente. Il
risultato conserva separatamente, per ogni slot, etichetta, seriale pubblico,
produttore, modello e relativi certificati. Un solo dispositivo viene compilato
automaticamente; se ne sono collegati più di uno la GUI richiede una scelta
esplicita. Il seriale viene conservato in esadecimale e passato alla
`TokenCriteria` pubblica di pyHanko, così dispositivi con la stessa etichetta non
vengono confusi. Per più certificati del dispositivo scelto viene analizzata
l'estensione X.509 Key Usage: un unico certificato `contentCommitment` viene
scelto come firma documenti, altrimenti le etichette sono presentate in una
finestra di scelta. Non viene effettuato il login sul token.

Il comando `Leggi card…` richiama lo stesso flusso e forza la visualizzazione
dell'inventario. Il probe decodifica dal certificato X.509 soltanto dati
pubblici: soggetto, emittente, intervallo di validità e Key Usage.

Per ogni certificato viene conservato anche il `CKA_ID` pubblico in formato
esadecimale. Durante la firma pyHanko riceve tale ID sia come `cert_id` sia come
`key_id`: il token può quindi associare certificato e chiave privata senza
richiedere che abbiano la stessa etichetta. Se l'utente specifica esplicitamente
`Chiave`, l'etichetta manuale mantiene la precedenza.

## Modello del batch

Ogni elemento conserva:

- fotografia iniziale del sorgente: percorso, dimensione e data di modifica;
- destinazione deterministica;
- stato corrente;
- codice e messaggio di errore, se presenti.

Prima della firma dimensione e data vengono ricontrollate. Gli stati terminali
sono `riuscito`, `saltato`, `errore` e `annullato`.

Le firme sono seriali perché non si presume che smart card e middleware siano
thread-safe. Il lavoro viene eseguito fuori dal thread grafico. Il percorso Qt
riceve eventi `BatchProgress` tipizzati per controllo, firma, verifica,
pubblicazione e completamento; l'annullamento viene controllato prima di
iniziare ogni file.

## Firma PDF

Il servizio PDF:

1. legge geometria, CropBox e rotazione dell'ultima pagina;
2. conta le firme incorporate già presenti;
3. costruisce `SignatureAppearanceData` dal certificato, dalle impostazioni e
   dal numero di firme già presenti;
4. genera con ReportLab una pagina PDF vettoriale temporanea con font Vera
   incorporato e la importa tramite l'API pubblica
   `StaticStampStyle.from_pdf_file()`;
5. aggiunge un campo dal nome casuale;
6. produce una firma PAdES con digest SHA-256;
7. scrive esclusivamente nel file temporaneo;
8. riapre il risultato e controlla che esista una firma in più;
9. verifica integrità e validità crittografica della nuova firma;
10. elimina sempre il PDF temporaneo dell'aspetto e lascia all'output service
    la pubblicazione del risultato.

La verifica usa il certificato del firmatario come ancora locale per isolare il
controllo crittografico. Non esegue una valutazione normativa, EUTL, OCSP o CRL.

Lo spike con pyHanko 0.37.0 ha confermato dimensioni esatte, testo estraibile,
font incorporato, resa vettoriale al 400%, firma e verifica. Non sono state
usate API private. Lo stesso renderer alimenta sia l'anteprima Qt sia la firma.

## Interfaccia Qt

`python -m mfirma` apre una `MSFluentWindow` con le sezioni
`Da firmare`, `Cronologia` e `Impostazioni`. La dashboard usa
`QAbstractTableModel` e `QSortFilterProxyModel`; selezione, ricerca e filtro non
dipendono dagli indici visibili. `ScanController` consegna il lavoro a un
`QThreadPool` e riporta alla UI un `ScanResult` immutabile. In caso di rete
assente l'ultima fotografia non viene cancellata.

`DiscoveryController` esegue `discover_pkcs11_modules` in `QThreadPool`. La DLL
continua a essere caricata soltanto dal probe figlio isolato: il worker Qt non
cambia il confine di sicurezza. I risultati pubblici alimentano modelli e
dialoghi dedicati; la scelta confermata conserva il seriale pubblico del token e
il `CKA_ID` del certificato, mantenendo l'inventario associato al singolo
dispositivo. `SettingsPage` costruisce un `AppConfig` validato, poi la finestra
lo salva atomicamente tramite `ConfigRepository`.

`PreviewController` legge CropBox, rotazione e firme esistenti fuori dal thread
grafico. Genera il PDF vettoriale dell'aspetto con lo stesso renderer della
firma, ne legge i byte e rimuove subito il temporaneo. `PreviewPage` affida a
`QPdfDocument/QPdfView` sia la pagina sorgente sia la rasterizzazione a 400% del
piccolo PDF vettoriale per lo schermo. L'overlay converte i movimenti in
`DisplayRect` espressi in punti e poi in `SignaturePlacement`; nessun pixel UI
entra nel piano di firma.

`PinDialog` consegna il PIN una sola volta al `SigningController`, lo cancella
subito dal widget e non lo inserisce in configurazione, segnali o stato globale.
Il controller esegue `BatchOrchestrator` in `QThreadPool`; il piano proveniente
dall'anteprima contiene coordinate PDF per singolo documento oppure un
rettangolo normalizzato condiviso. `ProgressPage` mostra gli eventi reali e
`ResultPage` espone solo messaggi utente classificati, non le eccezioni tecniche.

All'avvio `logging_setup.py` configura un file UTF-8 da 1 MiB con cinque copie
in `%LOCALAPPDATA%\mFirma\logs`. Il batch registra tipo, codice e dettaglio
tecnico degli errori dopo avere sostituito ogni occorrenza del PIN con
`[RISERVATO]`; non registra il contenuto dei PDF. Quando il riepilogo contiene
problemi, la UI mostra il percorso e consente di aprire direttamente il log.

`SystemTrayController` mantiene attiva l'applicazione quando la finestra viene
chiusa. `Esci` avvia uno shutdown non bloccante: richiede al batch di annullarsi
dopo il file corrente, attende scanner, discovery, anteprima e firma tramite un
timer Qt, quindi nasconde il tray e termina l'event loop. La GUI Tkinter e il
relativo adattatore sono stati rimossi.

Dimensione, posizione normale e stato massimizzato sono conservati in un JSON
separato accanto alla configurazione. Il repository accetta soltanto coordinate
e versione note, scrive mediante sostituzione atomica e non contiene dati dei
documenti o del dispositivo. Al ripristino Qt usa le geometrie disponibili in
pixel logici e riporta interamente la finestra nel monitor con maggiore
intersezione; uno stato completamente fuori schermo torna sul monitor primario.

## Confini intenzionali

- La GUI Qt non conosce le API interne di pyHanko o python-pkcs11.
- Lo scanner non firma e non scrive output.
- Il provider non decide nomi o posizioni.
- Il servizio PDF non salva né acquisisce il PIN.
- Il rilevatore non carica DLL nel processo della GUI e non seleziona moduli
  senza conferma dell'utente.
- Il fake provider esiste solo nei test.
