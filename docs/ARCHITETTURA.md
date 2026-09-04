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
- Il fake provider esiste solo nei test.

