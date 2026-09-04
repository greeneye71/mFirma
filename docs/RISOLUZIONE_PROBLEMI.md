# Risoluzione dei problemi

## L'applicazione non si avvia

- Verificare che esista `.venv\Scripts\pythonw.exe`.
- Dalla radice eseguire `.venv\Scripts\python -m mfirma` per vedere l'errore.
- Se manca un modulo, ripetere l'installazione da `requirements.lock`.

## DLL PKCS#11 non trovata

- Usare `Sfoglia…` e selezionare la DLL installata dal middleware ufficiale.
- Non scegliere una DLL generica o copiata da un altro PC.
- Controllare che applicazione e DLL siano entrambe x64.

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

