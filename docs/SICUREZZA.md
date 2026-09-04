# Sicurezza

## PIN e chiave privata

- La chiave privata rimane nel token.
- Il PIN viene richiesto solo quando l'utente conferma il batch.
- Il PIN non viene scritto nella configurazione, nei nomi file o nella riga di
  comando.
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

