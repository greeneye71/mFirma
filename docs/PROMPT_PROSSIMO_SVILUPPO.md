# Prompt per il prossimo sviluppo

Lavora nel repository mFirma aperto. Leggi integralmente, prima di modificare il
codice:

- `README.md`;
- `SPECIFICA_FIRMA_PDF_WINDOWS.md`;
- `docs/ARCHITETTURA.md`;
- `docs/PIANO.md`;
- `docs/SPECIFICA_INTERFACCIA.md`;
- `docs/SPECIFICA_ASPETTO_FIRMA.md`;
- `docs/SICUREZZA.md`;
- i moduli e i test esistenti.

Implementa il prossimo incremento reale del prodotto, non limitarti a un piano o
a un mockup. L'obiettivo è sostituire progressivamente la GUI Tkinter con
PySide6 + PySide6-Fluent-Widgets e introdurre il nuovo aspetto visibile della
firma PDF, mantenendo invariati i principi di sicurezza e il nucleo già testato.

Procedi in questo ordine.

## 1. Verifica iniziale

- Controlla lo stato Git e preserva modifiche non correlate.
- Esegui la suite corrente e registra il risultato iniziale.
- Individua i confini tra GUI, scanner, batch, provider, placement, output e
  servizio PDF.
- Non riscrivere scanner, orchestratore, provider o output se non serve per
  esporre un contratto pulito alla nuova UI.

## 2. Aspetto visibile della firma

Implementa per primo `docs/SPECIFICA_ASPETTO_FIRMA.md`.

- Introduci `SignatureAppearanceData`, la variante completa e quella compatta e
  un renderer indipendente dalla GUI.
- La variante completa predefinita misura 240 × 92 pt; la compatta 190 × 68 pt.
- Produci contenuto vettoriale con font incorporato. Esegui prima un piccolo
  spike con ReportLab + `StaticStampStyle.from_pdf_file()` usando esclusivamente
  API pubbliche della versione pyHanko bloccata. Se lo spike non soddisfa i
  requisiti, usa le API pubbliche di contenuto PDF di pyHanko e documenta la
  decisione.
- Mostra nome firmatario, organizzazione/ruolo se disponibili, data e ora con
  fuso o offset, motivo e luogo se compilati, emittente, profilo PAdES B-B,
  SHA-256 e numero progressivo della firma nel documento.
- Inserisci la frase neutra `Verificare la firma con un lettore PDF`.
- Non mostrare spunte verdi o testi che dichiarino firma valida, documento
  integro, certificato valido o marca temporale. La versione corrente è PAdES
  B-B senza TSA.
- Usa lo stesso renderer per anteprima e PDF firmato.
- Gestisci nomi lunghi, Unicode e campi mancanti senza overflow.
- Assicura cleanup deterministico di ogni file temporaneo.
- Mantieni la firma incrementale e la verifica crittografica già esistente.

Aggiungi test per modello dati, rendering, testo estraibile, font incorporato,
dimensioni, campi opzionali, timezone, quattro rotazioni, firma singola e
co-firma. Verifica visivamente almeno un PDF di test renderizzato al 400%.

## 3. Infrastruttura della nuova GUI

- Aggiungi PySide6, PySide6-Fluent-Widgets e le dipendenze strettamente
  necessarie; fissane le versioni in `requirements.lock` dopo uno smoke test su
  Windows.
- Crea il package `src/mfirma/ui/` seguendo la struttura proposta nella
  specifica.
- Mantieni `python -m mfirma` come comando di avvio.
- Usa `MSFluentWindow`, tema di sistema, colore principale `#2667D8` e Segoe UI.
- Implementa la navigazione `Da firmare`, `Cronologia`, `Impostazioni`.
- Non mantenere due GUI complete: `app.py` può essere un adattatore temporaneo,
  poi Tkinter va rimosso quando il flusso Qt è coperto.

## 4. Dashboard

- Implementa la pagina `Da firmare` come descritta nella specifica.
- Usa `QTableView` con `QAbstractTableModel` e `QSortFilterProxyModel`, mai
  `QTableWidget` per l'elenco principale.
- Conserva la selezione per percorso normalizzato, non per indice di riga.
- Implementa filtro per persona, ricerca differita, ordinamento e selezione di
  tutti i risultati visibili.
- Collega lo scanner esistente tramite worker Qt senza bloccare il thread GUI.
- Mostra correttamente cartella, dispositivo e certificato, inclusi gli stati di
  rete assente, token assente, scansione, warning e lista vuota.
- Il pulsante `Prepara la firma` è disponibile solo con almeno un documento
  selezionato.

## 5. Anteprima e flusso firma

- Usa `QPdfDocument` e `QPdfView` per la pagina `Controlla e firma`.
- Mostra il vero aspetto vettoriale come overlay, con i quattro preset,
  trascinamento, ridimensionamento, zoom e vincoli dentro CropBox.
- Riusa `placement.py` per la conversione delle coordinate e per le rotazioni;
  non salvare coordinate pixel della UI.
- Implementa il dialogo PIN senza persistenza, logging o passaggio nello stato
  globale.
- Collega `BatchOrchestrator` mediante segnali ed eventi strutturati.
- Implementa avanzamento reale, file corrente, fase, conteggi e `Annulla dopo il
  file corrente`.
- Implementa il riepilogo finale per riusciti, errori, saltati e annullati.

## 6. Impostazioni, certificati e tray

- Migra tutti i campi della GUI attuale nella pagina `Impostazioni`.
- Collega `ConfigRepository` e gestisci in modo retrocompatibile i nuovi valori
  dell'aspetto firma.
- Migra rilevamento DLL, lettura card e scelta certificato senza cambiare le
  garanzie del probe isolato.
- Implementa `QSystemTrayIcon`: chiudere la finestra deve nasconderla, mentre
  `Esci` deve chiudere ordinatamente worker e sessioni.
- Implementa la cronologia soltanto con dati realmente persistiti; non mostrare
  dati simulati nella build.

## 7. Qualità e sicurezza

- Nessuna operazione lenta nel thread GUI.
- Nessun PIN in configurazione, log, eccezioni mostrate, segnali generici o
  cronologia.
- Nessuna sovrascrittura silenziosa e nessuna modifica del sorgente.
- Un errore relativo a un PDF non interrompe il resto del batch.
- Mantieni messaggi orientati all'utente e dettagli tecnici nei log.
- Supporta tastiera, focus visibile, temi chiaro/scuro e scaling Windows 100%,
  125%, 150% e 200%.
- Non introdurre API private o dipendenze non necessarie senza motivazione.

## 8. Verifica e consegna

- Aggiungi test Qt con `pytest-qt` o equivalente, inclusi smoke test offscreen,
  modello tabellare, filtri, selezione, impostazioni, eventi di avanzamento e
  annullamento.
- Esegui tutta la suite dopo ogni fase importante.
- Verifica manualmente l'avvio dell'app e il flusso con provider/test data
  simulati; non richiedere hardware per i test automatici.
- Aggiorna documentazione utente, architettura, installazione, dipendenze e
  changelog in base a ciò che è realmente implementato.
- Non dichiarare compatibilità hardware o validità legale senza collaudo reale.
- Alla fine riporta file modificati, decisioni tecniche, test eseguiti, risultati
  e limiti ancora aperti.

Lavora per incrementi verificabili e mantieni sempre il progetto avviabile. Se
una parte ampia non può essere completata in sicurezza nello stesso ciclo,
termina un confine verticale funzionante e testato, quindi indica esattamente il
passo successivo senza lasciare codice morto o una seconda GUI incoerente.
