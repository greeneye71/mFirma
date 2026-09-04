# Architettura

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
GUI Tkinter ───────> BatchOrchestrator
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
| `app.py` | Finestra, configurazione visibile, selezione, worker e avanzamento |
| `scanner.py` | Ricerca PDF, associazione alla persona, esclusioni e stabilità |
| `models.py` | Oggetti di dominio e stati dei job |
| `batch.py` | Deduplicazione, firma seriale, annullamento ed esiti indipendenti |
| `provider.py` | Apertura e chiusura della sessione PKCS#11 |
| `pdf_service.py` | Campo visibile, PAdES B-B e verifica della nuova firma |
| `placement.py` | Coordinate dei quattro preset e trasformazione per rotazione |
| `output.py` | Nome, file temporaneo e pubblicazione senza sovrascrittura |
| `config.py` | Validazione e persistenza atomica della configurazione non segreta |
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
processo Tkinter. Il risultato ritorna alla GUI tramite la stessa coda eventi
usata dagli altri worker; il percorso viene salvato soltanto dopo la scelta
dell'utente.

Lo stesso probe isolato viene eseguito su una DLL scelta manualmente. Le
etichette pubbliche vengono restituite alla GUI: una singola etichetta viene
compilata automaticamente. Per più certificati viene analizzata l'estensione
X.509 Key Usage: un unico certificato `contentCommitment` viene scelto come firma
documenti, altrimenti le etichette sono presentate in una finestra di scelta.
Non viene effettuato il login sul token.

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
thread-safe. Il lavoro viene eseguito fuori dal thread Tkinter e la GUI riceve
gli aggiornamenti tramite una coda.

## Firma PDF

Il servizio PDF:

1. legge geometria, CropBox e rotazione dell'ultima pagina;
2. conta le firme incorporate già presenti;
3. aggiunge un campo dal nome casuale;
4. produce una firma PAdES con digest SHA-256;
5. scrive esclusivamente nel file temporaneo;
6. riapre il risultato e controlla che esista una firma in più;
7. verifica integrità e validità crittografica della nuova firma;
8. lascia all'output service la pubblicazione del risultato.

La verifica usa il certificato del firmatario come ancora locale per isolare il
controllo crittografico. Non esegue una valutazione normativa, EUTL, OCSP o CRL.

## Confini intenzionali

- Tkinter non conosce pyHanko o python-pkcs11.
- Lo scanner non firma e non scrive output.
- Il provider non decide nomi o posizioni.
- Il servizio PDF non salva né acquisisce il PIN.
- Il rilevatore non carica DLL nel processo della GUI e non seleziona moduli
  senza conferma dell'utente.
- Il fake provider esiste solo nei test.
