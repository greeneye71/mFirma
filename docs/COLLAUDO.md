# Piano di collaudo

## Test automatici

Eseguire dalla radice:

```powershell
.venv\Scripts\python -m pytest -p no:cacheprovider
```

La suite copre:

- quattro preset su pagine ruotate 0, 90, 180 e 270 gradi;
- rifiuto di riquadri fuori pagina;
- scansione ricorsiva, conteggi per persona ed esclusione dei firmati;
- deduplicazione della selezione manuale;
- naming, temporanei e collisioni;
- persistenza della configurazione senza PIN;
- prosecuzione del batch dopo un errore relativo a un file;
- apertura di una sola sessione nel batch simulato;
- firma PAdES software e seconda firma incrementale sullo stesso PDF.

Il certificato software creato dai test è esclusivamente una fixture effimera e
non può essere usato dalla build applicativa.

## Collaudo dell'installazione

Su una copia pulita del progetto in Windows 11 x64:

1. verificare che `.venv` non sia presente;
2. eseguire `avvia_mFirma.cmd` con una connessione Internet disponibile;
3. verificare creazione di `.venv`, installazione e apertura dell'applicazione;
4. chiudere e riavviare, verificando che non reinstalli le dipendenze;
5. eseguire `installa_mFirma.cmd` e verificare che la riparazione sia idempotente;
6. ripetere in un percorso contenente spazi;
7. provare separatamente il messaggio mostrato in assenza di Python compatibile.

Il test su PC privo di Python resta rinviato al futuro pacchetto autonomo: lo
script attuale deve rilevare il requisito mancante, non incorporare Python.

## Dati necessari per il collaudo reale

- marca e modello del token;
- versione firmware, se disponibile;
- produttore e versione del middleware;
- percorso esatto della DLL PKCS#11;
- architettura della DLL;
- PDF non sensibili o anonimizzati rappresentativi;
- visualizzatore e criterio aziendale usati per la validazione.

## Sequenza con il dispositivo

### 1. Inventario e probe

1. Annotare i dati in `device-compatibility.md`.
2. Verificare che Python sia a 64 bit.
3. Eseguire `mfirma.probe` senza PIN.
4. Registrare token label, seriale, certificate label e ID disponibili.

### 2. Firma singola

1. Usare un PDF neutro di una pagina.
2. Firmarlo in basso a destra.
3. Verificare che il sorgente sia invariato.
4. Aprire l'output con il visualizzatore concordato.
5. Controllare firma incorporata, firmatario, integrità e resa visiva.

### 3. Firma multipla sul documento

1. Aggiungere manualmente il primo output.
2. Cambiare preset.
3. Firmare di nuovo, possibilmente con un secondo certificato.
4. Verificare che entrambe le firme risultino presenti e valide.

### 4. Batch

Procedere gradualmente con 10, 50 e 100 PDF. Registrare:

- durata;
- numero di richieste PIN;
- errori per file;
- comportamento dopo un PDF corrotto;
- permanenza degli output riusciti dopo annullamento.

### 5. Errori controllati

- token assente prima dell'avvio;
- token rimosso tra due file;
- annullamento del dialogo middleware;
- PIN errato una sola volta;
- certificato inesistente o non idoneo;
- output già esistente;
- sorgente modificato dopo la selezione;
- PDF cifrato o corrotto;
- cartella senza permesso di scrittura.

Non ripetere prove con PIN errato: alcuni dispositivi si bloccano dopo pochi
tentativi.

## Campione PDF

Il campione finale dovrebbe includere:

- A4 verticale e orizzontale;
- pagine ruotate;
- PDF multipagina;
- CropBox diverso da MediaBox;
- modulo PDF;
- PDF con una firma esistente;
- PDF cifrato;
- file corrotto;
- nomi con spazi, accenti e parentesi;
- percorsi locali e UNC.

## Criterio di uscita della versione 0.1.0

La combinazione hardware può essere dichiarata supportata soltanto dopo una
firma singola e una co-firma validate, un batch di almeno dieci file e verifica
che il PIN non compaia in configurazione o messaggi diagnostici salvati.
