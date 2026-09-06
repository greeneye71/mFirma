# Changelog

## Non rilasciato

- semplificata la dashboard: impostazioni in fondo alla navigazione, righe
  selezionate evidenziate per intero, percorso cartella e conteggio sul pulsante;
- aggiunte le modalità Manuale e Da cartella, senza attivare la futura modalità automatica;
- mostrato il CN come intestatario; selezione diretta dell'unico certificato
  Firma documenti, mantenendo la conferma del firmatario nel dialogo PIN;
- ridotta la larghezza del riquadro completo a 212,6 pt mantenendo l'altezza
  di 92 pt; margini standard di 8,5 pt e fuso numerico GMT;
- allineati i limiti di trascinamento alla scala e alla posizione reali del PDF;
- aggiunto il registro JSONL persistente per documento, con nome del firmatario,
  tessera, certificato, date UTC, impronta del PDF e UUID della postazione;
- spostata la scelta della tessera e del certificato nel flusso di firma, con
  nuova lettura a ogni batch e identità separata dalle impostazioni comuni;
- aggiunta la preferenza facoltativa del certificato per middleware e seriale
  della tessera, riproposta con conferma; supportate etichette di certificato uguali;
- aggiunta in Output la scelta della cartella dei file firmati e dell'azione
  sull'originale: conservazione, sostituzione dopo la firma o eliminazione dopo
  il salvataggio; protezione dalle collisioni e segnalazione degli errori di rimozione;
- aggiunto l'archivio locale, atomico e versionato degli ultimi 100 batch reali;
- completata la pagina `Cronologia` con riepilogo, dettaglio per documento e
  copia dell'identificativo batch;
- spostati caricamento e salvataggio della cronologia fuori dal thread GUI e
  esclusi messaggi tecnici e segreti dal formato persistito;
- aggiunti istanza singola per utente e protocollo locale versionato, limitato a
  100 percorsi PDF e 256 KiB senza comandi arbitrari;
- aggiunto un launcher leggero che inoltra i file alla finestra aperta o avvia
  l'applicazione senza caricare anticipatamente Fluent e il motore di firma;
- spostata la lettura dei PDF scelti in un worker; i file validi vengono
  selezionati senza avviare automaticamente la firma;
- aggiunti script simmetrici per registrare e rimuovere il verbo classico
  `Firma PDF con mFirma` sotto `HKCU`;
- documentata come opzione finale la normalizzazione dei PDF ibridi senza firme,
  mantenendo attivi i controlli rigorosi;
- aggiunto il log UTF-8 rotante in `%LOCALAPPDATA%\mFirma\logs`, con codice e
  dettaglio tecnico degli errori e riepilogo operativo del batch;
- aggiunti percorso e pulsante `Apri log errori` nel riepilogo dei batch con
  problemi;
- sanitizzati i dettagli del batch e degli errori imprevisti del worker prima
  della registrazione, con test esplicito che impedisce la persistenza del PIN;
- aggiunto l'inventario PKCS#11 per singolo token e un dialogo di scelta quando
  sono collegati più dispositivi;
- il seriale pubblico del token viene salvato in esadecimale e passato a
  pyHanko, evitando ambiguità tra token con la stessa etichetta;
- la scelta del certificato e del relativo `CKA_ID` è ora confinata al token
  selezionato;
- aggiunto uno stato finestra separato, validato e atomico per ripristinare
  dimensione, posizione e massimizzazione dentro i monitor disponibili;
- completati i comandi tastiera della dashboard (`Ctrl+F`, `Ctrl+A`, `F5`,
  `Spazio`, `Invio`, `Esc`) e i nomi accessibili dei controlli principali;
- rimossi colori testuali fissi dalla dashboard per rispettare la palette dei
  temi chiaro e scuro;
- resa PySide6/Fluent l'unica GUI e impostato `python -m mfirma` come avvio
  predefinito; rimossa l'interfaccia Tkinter;
- aggiunto il tray di sistema con azioni `Apri mFirma` ed `Esci`;
- la chiusura della finestra ora la nasconde, mentre l'uscita aspetta in modo
  asincrono tutti i worker e annulla la firma dopo il file corrente;
- collegato il flusso Qt reale a `BatchOrchestrator`, dalla conferma
  dell'anteprima al riepilogo finale;
- aggiunto un dialogo PIN effimero, senza persistenza, logging o trasporto nei
  segnali di avanzamento;
- aggiunte pagine Qt di avanzamento ed esito con fasi, file corrente, conteggi,
  annullamento dopo il file corrente e messaggi utente sanificati;
- il piano di posizionamento dell'anteprima viene ora applicato alla firma PDF
  mediante coordinate PDF esplicite o rettangolo normalizzato condiviso;
- aggiunti eventi `BatchProgress` e test Qt hardware-free per worker,
  cancellazione, riepilogo e integrazione della finestra;
- aggiunta la pagina Qt `Controlla e firma` basata su `QPdfDocument` e
  `QPdfView`, con ultima pagina reale, navigazione tra documenti e zoom;
- l'aspetto vettoriale condiviso viene rasterizzato da Qt al 400% solo per lo
  schermo e sovrapposto come riquadro trascinabile e ridimensionabile;
- aggiunte conversioni pubbliche tra punti PDF e pagina visualizzata, vincoli
  CropBox, quattro rotazioni e posizione normalizzata applicabile al batch;
- preparazione di geometria, numero firma e aspetto spostata in worker Qt con
  cleanup deterministico prima della consegna alla GUI;
- resa operativa la pagina impostazioni Qt con tutti i valori persistiti da
  `ConfigRepository`, validazione e nessun campo PIN;
- migrati nella GUI Qt il rilevamento asincrono dei middleware PKCS#11, il probe
  isolato della DLL e la lettura/selezione dei certificati pubblici della card;
- aggiunti modelli e dialoghi Qt per middleware e certificati, inclusi uso
  `contentCommitment`, intestatario, emittente, scadenza e associazione `CKA_ID`;
- aggiunta la prima dashboard PySide6/Fluent, avviabile con `--qt-dashboard`,
  con navigazione, `QTableView`, filtri e scanner asincrono;
- selezione dei documenti conservata per percorso normalizzato, ricerca con
  debounce di 200 ms e mantenimento dell'ultima lista quando la rete è assente;
- bloccate e verificate su Windows le dipendenze Qt e `pytest-qt`;
- sostituito il riquadro testuale minimo con un aspetto firma vettoriale
  completo/compatto, font incorporato e informazioni neutrali verificabili;
- aggiunti modello `SignatureAppearanceData`, numero progressivo della firma,
  timezone esplicito e cleanup deterministico del temporaneo dell'aspetto;
- aggiornati i valori predefiniti a 240 × 92 pt, con migrazione del precedente
  default 180 × 60 pt;
- aggiunto `installa_mFirma.cmd` per creare o riparare automaticamente `.venv`;
- `avvia_mFirma.cmd` prepara l'ambiente al primo avvio se necessario;
- aggiunte istruzioni per installare Python 3.13 tramite `winget`.
- aggiunto il rilevamento assistito delle DLL PKCS#11 x64 con probe isolato.
- lettura automatica e scelta guidata dell'etichetta del certificato dopo la
  selezione della DLL.
- associazione della chiave privata tramite ID PKCS#11 del certificato, senza
  presumere che le due etichette coincidano.
- aggiunto `Leggi card…`, con elenco dei certificati pubblici e dettagli su uso,
  intestatario, emittente e scadenza.
- gli errori del dispositivo durante la firma non sono più classificati come
  PDF non valido.

## 0.1.0 - 2026-09-04

- prima GUI Tkinter;
- scansione per persona e selezione multipla;
- firma visibile PAdES B-B tramite provider PKCS#11;
- batch seriale con una sessione e annullamento controllato;
- possibilità di aggiungere firme incrementali a un PDF già firmato;
- quattro preset con gestione delle rotazioni;
- output nella stessa cartella, temporaneo e senza sovrascrittura;
- verifica crittografica immediata della nuova firma;
- configurazione atomica senza PIN;
- probe pubblico PKCS#11;
- suite automatica e documentazione iniziale.
