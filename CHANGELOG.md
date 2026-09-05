# Changelog

## Non rilasciato

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
