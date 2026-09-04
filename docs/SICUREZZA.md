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
- L'applicazione elimina i propri riferimenti al PIN appena terminato il batch.
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

## Dati personali

Percorsi e nomi dei file possono contenere dati personali. La versione attuale
non scrive log applicativi persistenti. Le segnalazioni manuali devono essere
redatte prima della condivisione.

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
| PIN salvato per errore | schema config privo del campo e nessun logging persistente |
| Sorgente sovrascritto | destinazione separata per nome e scrittura temporanea |
| Output preesistente perso | collisione trattata come `saltato` |
| PDF cambiato dopo selezione | confronto dimensione e data di modifica |
| Firma solo grafica | verifica dell'oggetto firma incorporato |
| Errore su un file blocca tutti | esito indipendente per ogni job |
| DLL non autorizzata | percorso esplicito; provenienza da verificare operativamente |

## Rilevamento delle DLL

Il rilevatore esamina soltanto nomi compatibili nelle posizioni dei software
installati e nelle cartelle Windows previste. Prima del probe scarta i file che
non sono DLL PE x64. Il probe viene eseguito senza PIN in un processo separato
con timeout, così un crash del middleware non termina la GUI.

L'isolamento del processo non rende affidabile una DLL sconosciuta: prima di
selezionarla l'utente deve controllare percorso e produttore e deve usare
soltanto middleware ottenuto dal fornitore ufficiale del dispositivo.
