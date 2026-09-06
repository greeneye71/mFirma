# mFirma

Prima versione snella di un'applicazione Windows per firmare uno o più PDF con
firma **PAdES B-B** e smart card/token **PKCS#11**.

La documentazione completa parte dall'[indice dei documenti](docs/README.md).

La modalità implementata è volutamente una sola: firma visibile PAdES con
output nella stessa cartella e suffisso `_firmato`. Il batch è seriale e apre
una sola sessione PKCS#11; il middleware può comunque richiedere nuovamente il
PIN per ogni firma. PAdES usa aggiornamenti incrementali, quindi una firma già
presente viene preservata ed è possibile aggiungerne un'altra selezionando
manualmente il PDF firmato.

L'aspetto visibile predefinito è vettoriale e usa un font incorporato. Mostra
firmatario, data e ora con fuso, emittente, profilo PAdES B-B, SHA-256 e numero
progressivo della firma, senza formulare giudizi di validità o indicare una
marca temporale non presente.

## Installazione e avvio

Richiede Windows 11 x64, Python 3.11+ x64 e il middleware ufficiale del token.

Per l'uso normale, dopo aver scaricato il progetto, fare doppio clic su
`avvia_mFirma.cmd`. Al primo avvio lo script crea automaticamente l'ambiente
locale `.venv`, installa le dipendenze e avvia l'applicazione. La prima
preparazione richiede una connessione Internet e può durare alcuni minuti.

Per installare o riparare manualmente l'ambiente, fare doppio clic su
`installa_mFirma.cmd`. Eseguirlo anche dopo un aggiornamento del progetto se
sono cambiate le dipendenze.

Se Python non è installato, aprire PowerShell ed eseguire:

```powershell
winget install --id Python.Python.3.13 -e
```

Chiudere e riaprire il terminale dopo l'installazione di Python, quindi avviare
nuovamente `avvia_mFirma.cmd`.

Per preparare manualmente l'ambiente di sviluppo:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.lock
.venv\Scripts\python -m pip install -e . --no-deps
.venv\Scripts\python -m mfirma
```

`python -m mfirma` avvia l'interfaccia PySide6/Fluent completa, dalla scansione
al riepilogo della firma:

```powershell
.venv\Scripts\python -m mfirma
```

L'opzione storica `--qt-dashboard` resta accettata per compatibilità ma non è
più necessaria. La GUI Tkinter è stata rimossa. Chiudere la finestra la nasconde
nell'area di notifica; `Esci` dal menu dell'icona attende ordinatamente i worker
e, se necessario, annulla il batch dopo il file corrente.

Nella finestra:

1. scegli nelle impostazioni la modalità Manuale oppure Da cartella;
2. indica la DLL PKCS#11 e salva le impostazioni;
3. aggiorna l'elenco o aggiungi PDF manualmente;
4. seleziona più righe e premi `Prepara la firma`;
5. controlla l'anteprima e premi `Continua e firma`: scegli il certificato dalla
   tessera inserita, poi inserisci il PIN. Lascia il PIN vuoto soltanto se il
   middleware usa il proprio dialogo protetto.

Per aggiungere il comando classico `Firma PDF con mFirma` a Esplora file,
esegui `registra_menu_esplora.cmd`. La registrazione è limitata all'utente
corrente e può comparire sotto `Mostra altre opzioni` in Windows 11. Il comando
non firma immediatamente: inoltra fino a 100 PDF alla singola istanza dell'app,
li seleziona nella dashboard e richiede comunque conferma. Per rimuoverlo usa
`rimuovi_menu_esplora.cmd`.

Il PIN non viene salvato. In `Impostazioni → Output` puoi scegliere la cartella
dei file firmati e se conservare, sovrascrivere o eliminare gli originali.
Per impostazione predefinita gli originali vengono conservati; una copia firmata
già esistente viene saltata.

Per aggiungere una seconda firma allo stesso PDF, usa `Aggiungi PDF` sul primo
output firmato e scegli preferibilmente un altro preset, così i due riquadri
visibili non si sovrappongono.

Per ispezionare token e certificati pubblici senza chiedere il PIN:

```powershell
.venv\Scripts\python -m mfirma.probe "C:\percorso\middleware.dll"
```

Alcuni dispositivi non espongono certificati senza login: in quel caso il probe
lo segnala senza tentare PIN.

## Stato dell'MVP

Implementato:

- scansione ricorsiva per persona e selezione multipla;
- aggiunta manuale di PDF, inclusi PDF già firmati per la co-firma;
- quattro preset visibili e ultima pagina;
- batch seriale con annullamento tra un file e il successivo;
- sessione PKCS#11 condivisa dal batch;
- output temporaneo, destinazione configurabile e scelta fra conservazione, sostituzione o eliminazione dell'originale;
- controllo post-firma: una nuova firma incorporata, integra e
  crittograficamente valida;
- configurazione JSON senza PIN;
- probe PKCS#11 senza autenticazione e test del nucleo senza token.
- rilevamento assistito delle DLL PKCS#11 x64 installate, senza richiesta PIN.
- lettura della tessera e scelta del certificato a ogni firma, con elenco di
  etichetta, uso, intestatario, emittente e scadenza dei certificati pubblici.
- preferenza facoltativa per tessera e middleware: preseleziona il certificato
  presente sulla tessera, con conferma quando occorre scegliere; l'unico certificato Firma documenti viene usato direttamente.
- scelta esplicita del token quando più dispositivi sono collegati, con
  associazione stabile tramite seriale pubblico anche per etichette uguali.
- associazione tra certificato e chiave privata mediante ID PKCS#11 pubblico.
- aspetto firma vettoriale completo (212,6 × 92 pt) o compatto (190 × 68 pt),
  condiviso con l'anteprima Qt e con cleanup deterministico.
- prima dashboard PySide6/Fluent con navigazione, modello `QTableView`, ricerca
  differita, filtro per persona, selezione stabile e scansione in worker Qt.
- pagina impostazioni Qt completa, persistenza atomica, discovery DLL in worker
  e scelta guidata del middleware; certificato scelto nel flusso di firma.
- pagina `Controlla e firma` con `QPdfView`, vero PDF sorgente, aspetto prodotto
  dal renderer condiviso, zoom, quattro preset e riquadro trascinabile e
  ridimensionabile in punti PDF.
- dialogo PIN Qt effimero, worker del batch, fasi di avanzamento reali,
  annullamento controllato e riepilogo finale senza dettagli sensibili;
- applicazione al PDF firmato delle coordinate in punti o normalizzate scelte
  nella stessa anteprima Qt.
- tray di sistema con ripristino della finestra e uscita asincrona ordinata;
- GUI Qt come unico avvio e rimozione definitiva dell'interfaccia Tkinter.
- dimensione, posizione e stato massimizzato ripristinati in coordinate logiche
  dentro un monitor disponibile;
- comandi tastiera principali e nomi accessibili per dashboard, impostazioni,
  anteprima, avanzamento e risultati.
- log applicativo rotante in `%LOCALAPPDATA%\mFirma\logs\mfirma.log`, con
  dettagli tecnici sanitizzati e accesso dal riepilogo quando si verifica un
  problema.
- istanza singola per utente, launcher leggero e canale locale versionato per
  ricevere fino a 100 PDF da linea di comando o dal verbo classico di Esplora;
  importazione asincrona e selezione senza firma automatica.
- cronologia locale degli ultimi 100 batch, con data e fuso, certificato,
  conteggi, esito e dettaglio per documento; il salvataggio è atomico e non
  contiene PIN o messaggi tecnici grezzi.

Registro per documento in `signatures.jsonl`, senza il limite dei 100 lotti:
nome del firmatario, tessera, certificato, date UTC, UUID della postazione e
impronta SHA-256 del PDF. Dettagli in [Registro delle firme](docs/REGISTRO_FIRME.md).

Rimandato: modalità automatica PDF+JSON, database centrale, menu moderno di Esplora file, pacchetto
autonomo con installer Windows e provider CSP/CNG. Questi punti sono pianificati in
[docs/PIANO.md](docs/PIANO.md).

## Test

```powershell
.venv\Scripts\python -m pytest -p no:cacheprovider
```

I test automatici non provano la validità legale o la compatibilità hardware.
La scheda da compilare con dispositivo e file reali è in
[docs/device-compatibility.md](docs/device-compatibility.md).

## Documentazione

- [Manuale utente](docs/MANUALE_UTENTE.md)
- [Installazione](docs/INSTALLAZIONE.md)
- [Architettura](docs/ARCHITETTURA.md)
- [Specifica dell'interfaccia](docs/SPECIFICA_INTERFACCIA.md)
- [Aspetto visibile della firma](docs/SPECIFICA_ASPETTO_FIRMA.md)
- [Piano di collaudo](docs/COLLAUDO.md)
- [Risoluzione dei problemi](docs/RISOLUZIONE_PROBLEMI.md)
- [Sicurezza](docs/SICUREZZA.md)
- [Limiti noti](docs/LIMITI_NOTI.md)
- [Piano di progetto](docs/PIANO.md)
