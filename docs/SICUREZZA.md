# Sicurezza

## PIN e chiave privata

- La chiave privata rimane nel token.
- Il PIN viene richiesto solo quando l'utente conferma il batch.
- Il PIN non viene scritto nella configurazione, nei nomi file o nella riga di
  comando.
- L'ID PKCS#11 salvato per associare certificato e chiave è un identificativo
  pubblico, non contiene la chiave privata e non consente di ricostruirla.
- `Leggi card…` accede soltanto ai certificati pubblici e ai relativi metadati;
  non richiede il PIN e non legge né esporta la chiave privata.
- Il dialogo Qt consegna il PIN direttamente al worker una sola volta e pulisce
  il campo; stato globale, configurazione, cronologia e segnali Qt non lo
  contengono.
- Prima di associare un errore a un job, il batch rimuove dal messaggio ogni
  occorrenza del PIN ricevuto. La pagina di esito mostra comunque soltanto
  messaggi classificati e non le eccezioni tecniche.
- Il worker discovery Qt conserva l'isolamento esistente: non carica la DLL nel
  processo grafico e non effettua autenticazione sul token.
- Il worker di anteprima legge soltanto il PDF sorgente e produce in memoria i
  byte dell'aspetto dopo aver eliminato deterministicamente il temporaneo; la
  pagina Qt non scrive né modifica il documento mostrato.
- L'applicazione elimina i propri riferimenti al PIN appena terminato il batch.
- Lo stato finestra è separato dalla configurazione e ammette soltanto versione,
  coordinate logiche, dimensioni e indicatore di massimizzazione; la scrittura
  è atomica e non include PIN, token o percorsi dei documenti.
- Python non può garantire l'azzeramento di tutte le copie in memoria.
- Se il middleware offre un dialogo protetto, l'utente può lasciare vuoto il
  campo dell'applicazione e usare il dialogo del produttore.

## Protezione dei documenti

- Il sorgente viene aperto in lettura e non viene sostituito.
- L'output esistente non viene sovrascritto.
- La firma viene prodotta in un temporaneo nella destinazione.
- Il temporaneo diventa definitivo soltanto dopo il controllo della nuova
  firma.
- Un errore provoca la rimozione del temporaneo, per quanto consentito dal file
  system.
- Dimensione e data del sorgente vengono ricontrollate subito prima della firma.
- Il PDF temporaneo usato per l'aspetto visibile contiene soltanto dati pubblici
  del certificato e impostazioni confermate; viene eliminato deterministicamente
  dopo successo o errore.

## Validazione

Il controllo automatico conferma che la nuova firma è presente, integra e
crittograficamente valida. Non sostituisce:

- verifica della catena di certificazione;
- controllo di revoche OCSP/CRL;
- verifica rispetto a liste fiduciarie europee;
- marca temporale TSA;
- valutazione legale del processo organizzativo.

Questi aspetti richiedono una policy concordata e, se necessari, un'evoluzione
verso PAdES B-T, B-LT o B-LTA.

## Log e dati personali

Il log applicativo persistente è salvato in
`%LOCALAPPDATA%\mFirma\logs\mfirma.log`, è limitato a 1 MiB e conserva cinque
copie. Registra eventi operativi ed errori tecnici, ma non il contenuto dei PDF
né il PIN. Prima della registrazione il batch sostituisce ogni occorrenza del
PIN ricevuto con `[RISERVATO]`; anche l'errore imprevisto del worker viene
sanitizzato prima di attraversare il segnale Qt.

Nomi dei file, etichette di token e certificati e messaggi restituiti dal
middleware possono comunque contenere dati personali. Il log deve quindi
restare nel profilo locale dell'utente ed essere controllato e redatto prima
della condivisione.

La cronologia è un archivio distinto in
`%LOCALAPPDATA%\mFirma\history.json`. Conserva percorsi dei documenti e degli
output riusciti, persona ricavata dalla cartella, etichetta pubblica del
certificato, stato e codice classificato dell'errore. Non conserva PIN,
eccezioni o messaggi tecnici grezzi. È limitata agli ultimi 100 batch, validata
in lettura e aggiornata mediante sostituzione atomica in un worker Qt. Poiché i
percorsi possono essere dati personali, il file non deve essere condiviso
senza verifica e può essere eliminato a programma chiuso.

## Dipendenze

Le dipendenze sono bloccate in `requirements.lock`. Prima di distribuire una
release pilota occorre:

- verificare vulnerabilità note;
- ricostruire il pacchetto in ambiente pulito;
- validare hash e provenienza degli artefatti;
- non redistribuire la DLL del produttore senza licenza;
- firmare eseguibili e installer, se disponibile un certificato di code signing.

`installa_mFirma.cmd` scarica i pacchetti tramite `pip` al primo utilizzo. Le
versioni sono fissate, ma il lock attuale non contiene hash degli artefatti:
l'installazione va quindi eseguita soltanto su reti e indici Python considerati
affidabili. Il futuro pacchetto di distribuzione dovrà usare artefatti verificati
e riproducibili.

## Modello di minaccia essenziale

| Rischio | Controllo attuale |
|---|---|
| PIN salvato per errore | schema config privo del campo e sanitizzazione prima di job, segnali e log |
| Sorgente sovrascritto | destinazione separata per nome e scrittura temporanea |
| Output preesistente perso | collisione trattata come `saltato` |
| PDF cambiato dopo selezione | confronto dimensione e data di modifica |
| Firma solo grafica | verifica dell'oggetto firma incorporato |
| Errore su un file blocca tutti | esito indipendente per ogni job |
| DLL non autorizzata | percorso esplicito; provenienza da verificare operativamente |
| Richiesta IPC arbitraria | socket per utente, schema versionato, soli PDF assoluti e limiti 100 file/256 KiB |

## IPC e integrazione con Esplora file

Il server locale usa l'opzione Qt che limita l'accesso all'utente corrente. Non
accetta azioni arbitrarie: una richiesta contiene soltanto versione e percorsi
PDF assoluti, con limiti espliciti. I percorsi vengono comunque verificati in un
worker prima di entrare nella coda e non avviano mai la firma automaticamente.

Gli script del verbo classico scrivono esclusivamente sotto `HKCU` e dispongono
di una rimozione simmetrica. Il componente eseguito da Esplora è il launcher;
provider, DLL PKCS#11 e PIN restano nel processo applicativo.

## Rilevamento delle DLL

Il rilevatore esamina soltanto nomi compatibili nelle posizioni dei software
installati e nelle cartelle Windows previste. Prima del probe scarta i file che
non sono DLL PE x64. Il probe viene eseguito senza PIN in un processo separato
con timeout, così un crash del middleware non termina la GUI.

L'isolamento del processo non rende affidabile una DLL sconosciuta: prima di
selezionarla l'utente deve controllare percorso e produttore e deve usare
soltanto middleware ottenuto dal fornitore ufficiale del dispositivo.
