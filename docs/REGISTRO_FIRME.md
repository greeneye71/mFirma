# Registro delle firme

Ogni documento elaborato produce una riga JSON nel file locale
`%LOCALAPPDATA%\mFirma\signatures.jsonl`. Il registro è distinto da
`history.json`, che contiene soltanto gli ultimi 100 lotti. Il registro non
viene troncato automaticamente e non ha il limite dei 100 lotti.

La pagina Cronologia indica il percorso effettivo e consente di aprire la
cartella del registro. Se l'applicazione usa una configurazione in un'altra
directory, anche registro e identità della postazione sono in quella directory.

## Dati per documento (schema_version 1)

| Campo | Contenuto |
|---|---|
| operation_id | UUID dell'operazione sul singolo documento |
| batch_id | UUID del lotto, uguale a quello nella cronologia |
| workstation_id, workstation_name | UUID locale persistente e nome della postazione |
| file_name, source_path | Nome e percorso del PDF originale |
| output_name, output_path | Nome e percorso previsto per il PDF firmato |
| signature_saved | Indica se il nuovo PDF firmato è stato effettivamente pubblicato |
| output_sha256 | SHA-256 del contenuto firmato salvato; null se non salvato |
| signer_name | Nome del firmatario, ricavato dal CN del certificato; ripiego su intestatario completo o etichetta |
| token_label, token_serial | Etichetta e seriale pubblico PKCS#11 della tessera, codificato in esadecimale |
| certificate_label, certificate_id | Etichetta e ID pubblico PKCS#11 del certificato |
| certificate_serial, certificate_sha256 | Numero seriale X.509 in decimale e impronta SHA-256 del certificato DER |
| certificate_subject, certificate_issuer | Intestatario completo ed emittente del certificato |
| signed_at_utc | Ora del computer utilizzata per il riquadro della firma, convertita in UTC; null prima della firma |
| completed_at_utc | Data e ora UTC di completamento dell'operazione sul documento |
| mode | manual oppure folder |
| source_action | keep, overwrite oppure delete |
| status, error_code | Esito complessivo e codice classificato dell'eventuale errore |

Le date sono ISO 8601 con offset `+00:00`. La data della firma è l'ora dichiarata
dalla postazione, non una marca temporale. I metadati assenti nel middleware
rimangono vuoti; non vengono inventati. Il PIN, la chiave privata e i messaggi
tecnici grezzi non vengono registrati.

La presenza di `output_path` non prova che il file sia stato creato:
controllare `signature_saved`. Per esempio, se il file di destinazione esiste
già, il risultato è `saltato` e `signature_saved` è false. Se il PDF firmato è
stato salvato ma l'eliminazione dell'originale è fallita, `signature_saved` è
true e `error_code` è `SOURCE_DELETE_FAILED`.

## Scrittura e problemi

Il worker scrive e sincronizza ogni riga su disco prima di passare al documento
successivo. Sono registrati anche errori, file saltati e annullamenti. Il
registro viene controllato prima di aprire la sessione di firma: se non è
scrivibile, non vengono firmati documenti.

Se la scrittura fallisce dopo il salvataggio di una firma, il PDF firmato viene
conservato, il risultato segnala il problema e il resto del lotto non viene
firmato. Non è possibile garantire una registrazione su un disco non scrivibile.
Il registro JSONL e il PDF sono due file distinti: un arresto del processo o
della macchina tra i due salvataggi può richiedere una riconciliazione manuale.

Una riga finale incompleta viene rilevata e conservata senza sovrascriverla;
prima di riprendere le firme, copiare il registro per sicurezza e far verificare
l'ultima registrazione. Non eliminare l'intero registro per risolvere un errore.
Prevedere copie di sicurezza: il JSONL è modificabile da chi ha accesso alla
cartella e non costituisce un archivio immodificabile.

## Identità della postazione e sviluppo futuro

`workstation.json` viene creato al primo utilizzo del registro e contiene l'UUID
persistente della postazione. Va conservato negli aggiornamenti. Nel preparare
una nuova postazione non copiare questo file da un'altra macchina: lasciare che
sia generata una nuova identità locale. Il nome della postazione è quello
registrato alla prima creazione dell'identità.

Il registro espone un'interfaccia separata dal motore di firma; schema,
identificativi globali e date UTC consentiranno l'alimentazione di un database
comune da più postazioni. In una fase futura l'invio dovrà essere ripetibile
senza duplicazioni, usando operation_id come chiave e mantenendo uno stato di
sincronizzazione separato dal registro locale. Nessun invio, connessione al
database o sincronizzazione è implementato in questa versione.

La cronologia precedente non viene convertita retroattivamente: non contiene
tutti i dati necessari per compilare il registro in modo attendibile.
