# Risoluzione dei problemi

## L'applicazione non si avvia

- Eseguire `installa_mFirma.cmd` e leggere l'eventuale errore mostrato.
- Verificare che Python 3.11 o successivo a 64 bit sia installato.
- Verificare che la prima installazione possa accedere a Internet.
- Dalla radice eseguire `.venv\Scripts\python -m mfirma` per vedere l'errore.
- Se manca un modulo, `installa_mFirma.cmd` ripete l'installazione da
  `requirements.lock` e ripara l'ambiente.

## Python non trovato o versione non compatibile

Lo script richiede Python 3.11 o successivo a 64 bit. In PowerShell eseguire:

```powershell
winget install --id Python.Python.3.13 -e
```

Chiudere e riaprire PowerShell prima di riprovare. Se `winget` non è
disponibile, installare CPython x64 dal sito ufficiale Python e abilitare il
Python Launcher durante l'installazione.

## Installazione delle dipendenze non riuscita

- controllare la connessione Internet;
- su una rete aziendale verificare con l'amministratore proxy, certificati TLS
  e accesso all'indice Python usato dall'organizzazione;
- chiudere eventuali antivirus o strumenti che tengono bloccata `.venv`, senza
  disattivare le protezioni aziendali;
- eseguire nuovamente `installa_mFirma.cmd` per tentare la riparazione;
- se continua a fallire, rinominare `.venv` in `.venv_old` e ripetere
  l'installazione per creare un ambiente pulito.

Conservare il messaggio completo mostrato nella finestra: indica quale fase tra
creazione dell'ambiente, dipendenze e installazione di mFirma non è riuscita.

## DLL PKCS#11 non trovata

- Premere `Rileva…` dopo aver installato il middleware ufficiale.
- Usare `Sfoglia…` e selezionare la DLL installata dal middleware ufficiale.
- Non scegliere una DLL generica o copiata da un altro PC.
- Controllare che applicazione e DLL siano entrambe x64.

Il rilevamento è intenzionalmente prudente e può non riconoscere nomi o
posizioni non comuni. Se il modulo selezionato manualmente funziona, annotarne
percorso e produttore in `device-compatibility.md` per estendere le future
regole di ricerca.

## Etichetta del certificato non nota

Collegare il token e scegliere la DLL con `Rileva…` oppure `Sfoglia…`. mFirma
legge le etichette pubbliche senza PIN: compila automaticamente una singola
etichetta, preferisce l'unico certificato con uso `contentCommitment` oppure
mostra una finestra se la scelta tra più certificati resta ambigua. Se non
compare alcuna etichetta, il token può richiedere il login anche per
l'enumerazione pubblica; consultare il middleware del produttore.

Un errore tipo `%1 non è un'applicazione Win32 valida` spesso indica una
differenza tra architettura x86 e x64.

## Nessun token o certificato

1. Chiudere gli altri programmi che potrebbero tenere occupato il dispositivo.
2. Rimuovere e reinserire token o smart card.
3. Verificare il dispositivo con il software del produttore.
4. Eseguire il probe.
5. Controllare esattamente maiuscole, spazi ed etichetta del certificato.

Alcuni token non permettono l'enumerazione pubblica senza login: il fallimento
del probe non dimostra da solo che il token sia incompatibile.

## Il PIN viene chiesto più volte

È un comportamento possibile. Il batch riusa la sessione, ma token e middleware
possono imporre una nuova autenticazione per ogni firma. Non aumentare il numero
di tentativi automatici e non salvare il PIN.

## PIN errato o bloccato

Non riprovare automaticamente. Usare il software ufficiale del dispositivo per
controllare lo stato. Il programma non può conoscere il numero di tentativi
rimasti se il middleware non lo comunica.

## Un PDF viene saltato

La causa più comune è la presenza del corrispondente `_firmato.pdf`. Il
comportamento è intenzionale e impedisce sovrascritture. Spostare o rinominare
l'output solo dopo averne verificato il contenuto.

## Il file è cambiato dopo la selezione

Aggiornare la cartella e ripetere la selezione. Questo controllo impedisce di
firmare una versione diversa da quella confermata.

## PDF cifrato, corrotto o non leggibile

Aprire il file con un visualizzatore affidabile. La versione 0.1.0 non gestisce
password PDF. L'errore riguarda soltanto quel file; il batch prosegue.

## Impossibile scrivere l'output

- verificare i permessi della cartella;
- controllare spazio libero e connessione di rete;
- chiudere un eventuale output aperto da un altro programma;
- verificare che antivirus o protezione ransomware non blocchino Python.

Il temporaneo viene creato nella cartella di destinazione per rendere la
pubblicazione finale atomica sullo stesso volume.

## Riquadro firma nella posizione errata

Provare un altro preset e annotare dimensione pagina, CropBox e rotazione nel
campione di collaudo. La resa deve essere validata sui PDF reali prima del pilot.

## Informazioni da fornire per una segnalazione

- versione mFirma;
- versione Windows;
- modello token e middleware;
- architettura e percorso DLL;
- fase che fallisce: probe, apertura sessione, firma o verifica;
- messaggio completo, oscurando percorsi e dati personali se necessario;
- PDF di esempio anonimizzato, quando possibile.

Non inviare PIN, chiavi private o schermate che mostrino dati riservati.
