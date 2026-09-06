# Manuale utente

## A cosa serve

mFirma firma uno o più documenti PDF usando il certificato presente in una
smart card o token USB. La versione 0.1.0 crea firme visibili PAdES B-B tramite
PKCS#11.

Ogni PDF viene elaborato separatamente: un documento problematico non impedisce
di tentare quelli successivi. Il programma non firma automaticamente i file
presenti nella cartella.

## Prima dell'avvio

Verificare che:

1. Python 3.11 o successivo a 64 bit sia installato;
2. al primo avvio sia disponibile una connessione Internet;
3. il middleware ufficiale del token sia installato;
4. token o smart card siano collegati;
5. la DLL PKCS#11 sia a 64 bit, come Python e l'applicazione;
6. sia installata la DLL PKCS#11; percorso ed etichette possono essere rilevati
   da mFirma;
7. l'utente abbia permesso di lettura e scrittura nelle cartelle dei PDF.

## Avvio

Fare doppio clic su `avvia_mFirma.cmd`.

Al primo avvio si apre una finestra di preparazione che:

1. verifica la presenza di Python 3.11+ a 64 bit;
2. crea l'ambiente locale `.venv`;
3. installa le dipendenze indicate in `requirements.lock`;
4. installa mFirma nell'ambiente locale;
5. apre l'applicazione al termine.

La preparazione può durare alcuni minuti. Agli avvii successivi la finestra
non viene mostrata se l'ambiente è completo.

Se viene segnalata l'assenza di Python, aprire PowerShell ed eseguire:

```powershell
winget install --id Python.Python.3.13 -e
```

Chiudere e riaprire PowerShell dopo l'installazione, quindi fare nuovamente
doppio clic su `avvia_mFirma.cmd`.

Per riparare l'ambiente eseguire `installa_mFirma.cmd`. Per avviare
l'applicazione dal terminale, dalla radice del progetto eseguire:

```powershell
.venv\Scripts\python -m mfirma
```

Il comando apre direttamente la GUI Qt, che consente scansione, ricerca,
filtro, impostazioni, rilevamento middleware, lettura card, anteprima PDF e
firma completa. L'opzione storica `--qt-dashboard` è ancora accettata ma non è
necessaria.

Nella finestra selezionare uno o più documenti e premere `Prepara la firma`.
La pagina `Controlla e firma` apre l'ultima pagina del primo PDF. È possibile
cambiare documento, adattare lo zoom, scegliere uno dei quattro preset e
trascinare o ridimensionare il riquadro restando all'interno della pagina. La
data mostrata è dichiaratamente dimostrativa e viene rigenerata durante la
firma.

Premendo `Continua e firma` viene richiesto il PIN in un dialogo dedicato. Il
valore viene consegnato una sola volta al worker e cancellato dal campo; se il
middleware mostra un proprio dialogo protetto, selezionare l'opzione apposita e
non inserire il PIN in mFirma. La pagina successiva mostra file corrente, fase,
conteggi e avanzamento. `Annulla dopo il file corrente` non interrompe
bruscamente il middleware. Al termine il riepilogo distingue riusciti, errori,
saltati e annullati senza mostrare dettagli tecnici potenzialmente sensibili.

## Cronologia

La sezione `Cronologia` mostra gli ultimi 100 batch effettivamente conclusi e
salvati sul PC. Per ogni batch sono indicati data e ora con offset, certificato,
numero di documenti ed esito sintetico. Selezionando una riga si vedono gli
esiti dei singoli documenti; `Copia ID batch` copia l'identificativo utile per
correlare una segnalazione con il log.

La cronologia è locale al profilo Windows e non certifica la validità legale
della firma. Non contiene il PIN né i messaggi tecnici grezzi del middleware.
Se l'archivio non è leggibile, l'applicazione continua a firmare e segnala il
problema nella pagina e nel log.

## Area di notifica e uscita

Il pulsante di chiusura della finestra nasconde mFirma senza interrompere
scansioni o firme. Per riaprire la finestra usare `Apri mFirma` dal menu
dell'icona nell'area di notifica di Windows. Per terminare davvero il programma
scegliere `Esci`: se una firma è in corso, mFirma completa il documento corrente,
annulla quelli non ancora iniziati, attende la chiusura dei worker e poi esce.

La dimensione, la posizione normale e lo stato massimizzato della finestra
vengono ricordati. Se il monitor usato in precedenza non è più collegato, mFirma
riporta la finestra dentro un monitor disponibile.

## Comandi da tastiera

- `Ctrl+F`: porta il cursore nella ricerca;
- `Ctrl+A`: seleziona o deseleziona tutti i risultati visibili quando la tabella
  è attiva;
- `F5`: aggiorna la cartella;
- `Spazio`: seleziona o deseleziona le righe evidenziate;
- `Invio`: prepara la firma dei documenti selezionati;
- `Esc`: dall'anteprima o dal riepilogo torna all'elenco dei documenti.

## Configurazione iniziale

L'icona `Impostazioni` si trova in fondo alla barra laterale, separata dalle
funzioni operative. Non richiede password.

Scegliere la modalità di lavoro:

- `Manuale`: aggiunta esplicita dei PDF, senza scansioni della cartella.
- `Da cartella`: scansione della directory configurata e filtro per sottocartella;
  resta disponibile anche l'aggiunta manuale. È il valore iniziale per le installazioni esistenti.

La modalità automatica sarà definita in seguito e non è selezionabile.
Salvare le impostazioni per applicare la modalità. Al cambio modalità o cartella
l'elenco viene svuotato per evitare di firmare documenti del contesto precedente.

In `Impostazioni` compilare:

| Campo | Significato |
|---|---|
| Cartella da firmare | Radice che contiene una sottocartella per ogni persona |
| DLL PKCS#11 | Libreria installata dal middleware; usare `Rileva…` o `Sfoglia…` |
| Posizione | Angolo della pagina in cui mostrare il riquadro firma |
| Aspetto | `Completo` (212,6 × 92 pt) oppure `Compatto` (190 × 68 pt) |

Premere `Salva impostazioni` per rendere effettiva la configurazione. Il PIN non
fa parte della configurazione.

L'aspetto completo mostra i dati pubblici essenziali del firmatario, la data e
l'ora del computer con il fuso numerico (GMT+1 o GMT+2, secondo la data), il profilo PAdES B-B, SHA-256 e il numero della
firma nel documento. La frase `Verificare la firma con un lettore PDF` è
intenzionalmente neutra: il riquadro non dichiara la validità legale, la fiducia
del certificato o la presenza di una marca temporale TSA.

### Rilevare automaticamente la DLL

Premere `Rileva…` accanto a `DLL PKCS#11`. mFirma cerca candidate nelle cartelle
dei programmi installati e nelle posizioni standard di Windows, accetta
soltanto DLL x64 e verifica l'interfaccia PKCS#11 in un processo separato. Il
controllo non richiede il PIN e può durare alcuni secondi.

La finestra mostra percorso, eventuali token collegati e origine della
candidata. Selezionare una riga e premere `Usa selezionata`, oppure fare doppio
clic, quindi salvare le impostazioni. Un middleware valido può comparire anche
senza tessere inserite. Se la ricerca non trova nulla, usare `Sfoglia` e indicare
la DLL documentata dal produttore.

### Scegliere il certificato al momento della firma

La configurazione comune contiene il middleware, senza un firmatario globale.
Ogni persona inserisce la propria tessera prima di premere `Continua e firma`.
L'anteprima serve a posizionare la firma e usa dati dimostrativi; i dati reali
del firmatario vengono letti dalla tessera durante il flusso di firma.

1. Dopo `Continua e firma`, mFirma rilegge i dispositivi e i certificati pubblici.
2. Se sono presenti più tessere, scegliere quella da usare nell'elenco con
   etichetta, seriale, produttore, modello e slot.
3. Se sulla tessera c'è un solo certificato `Firma documenti`, viene usato
   direttamente, anche in presenza di certificati di autenticazione.
   Altrimenti scegliere il certificato nell'elenco: l'intestatario mostra il
   nome CN; i dati completi sono disponibili passando il mouse sulla riga.
   Senza CN viene mostrato l'intestatario completo o l'etichetta.
4. Se compare l'elenco, è possibile selezionare `Ricorda la scelta per questa tessera`.
5. Premere `Usa certificato`, controllare intestatario e tessera nel dialogo PIN,
   quindi confermare la firma.

La preferenza memorizza solo l'ID pubblico del certificato, associato al
middleware e al seriale della tessera. Alla firma successiva sulla stessa
tessera viene preselezionato il certificato quando è necessaria una scelta.
La regola dell'unico certificato Firma documenti ha precedenza sulla preferenza.
Se il certificato non è più presente viene proposta una nuova scelta. Togliere
la spunta per dimenticare la preferenza della tessera corrente. Il PIN non
viene mai memorizzato. Certificati senza ID pubblico non possono essere ricordati.

Le vecchie selezioni globali non vengono usate per firmare. La scelta del
certificato e della relativa chiave vale soltanto per il batch corrente.
Il seriale identifica la tessera anche se un'altra ha la stessa etichetta:
se viene sostituita prima dell'apertura della sessione, la firma non ripiega
automaticamente sull'altra tessera. Se il middleware non espone il seriale o
certificati pubblici leggibili, il flusso si interrompe con un messaggio.

## Caricare i documenti

### Da Esplora file

Eseguire una volta `registra_menu_esplora.cmd` per aggiungere il comando
`Firma PDF con mFirma` all'utente Windows corrente. In Windows 11 il verbo
classico può essere visibile sotto `Mostra altre opzioni`.

Selezionare fino a 100 PDF, aprire il menu contestuale e scegliere il comando.
Se mFirma è già aperta, la finestra viene ripristinata; altrimenti viene avviata.
I file validi vengono aggiunti e selezionati nella dashboard, ma la firma non
parte finché non si preme `Prepara la firma` e non si conferma l'anteprima.

Per eliminare l'integrazione eseguire `rimuovi_menu_esplora.cmd`. La selezione
multipla dal verbo classico deve ancora essere collaudata sulla postazione reale;
in alternativa è sempre disponibile `Aggiungi PDF`.

### Dalla cartella organizzata per persona

La struttura attesa è:

```text
Da firmare\
├── Mario Rossi\
│   ├── documento.pdf
│   └── pratica\allegato.pdf
└── Lucia Bianchi\
    └── contratto.pdf
```

Premere `Aggiorna cartella`. La scansione:

- cerca PDF nelle sottocartelle;
- associa ogni file alla cartella di primo livello;
- ignora estensioni diverse da `.pdf`;
- ignora i nomi che terminano con `_firmato.pdf`;
- ignora temporaneamente file modificati da meno di cinque secondi.

### Aggiunta manuale

Premere `Aggiungi PDF…` e scegliere uno o più file. Questa modalità permette
anche di selezionare un PDF già firmato per aggiungere una firma successiva.

## Firmare un gruppo di PDF

1. Selezionare le righe desiderate. Usare `Ctrl` o `Maiusc` per una selezione
   multipla, oppure `Seleziona tutti`.
2. Premere `Firma selezionati`.
3. Controllare il riepilogo: numero di documenti, profilo, posizione e suffisso.
4. Confermare.
5. Inserire il PIN. Lasciarlo vuoto solo se il middleware gestisce un proprio
   dialogo protetto.
6. Attendere il riepilogo finale.

Se uno o più documenti non vengono firmati, il riepilogo mostra il pulsante
`Apri log errori`. Il file diagnostico si trova normalmente in:

```text
%LOCALAPPDATA%\mFirma\logs\mfirma.log
```

Il log indica data, componente, codice e dettaglio tecnico dell'errore. Prima
di inviarlo ad altri, controllarlo perché nomi di file, etichette del dispositivo
o del certificato possono contenere dati personali. Il PIN viene rimosso dai
messaggi del batch e non deve comparire nel log.

La sessione PKCS#11 viene aperta una volta per il batch, ma il dispositivo può
richiedere nuovamente il PIN per ogni documento. Questo comportamento dipende
dal token e non può essere imposto dall'applicazione.

## Risultato

Per impostazione predefinita, per `documento.pdf` viene creato nella stessa cartella:

```text
documento_firmato.pdf
```

In `Impostazioni → Output`, scegli la cartella con `Sfoglia` oppure lascia il
campo vuoto per usare la cartella dell'originale. Seleziona l'azione sul file
originale e premi `Salva impostazioni` prima di avviare la firma:

- `Conserva l'originale`: salva la copia firmata con il suffisso configurato.
- `Sovrascrivi l'originale con il file firmato`: sostituisce l'originale mantenendo
  il suo nome e percorso; cartella di output e suffisso non vengono usati.
- `Elimina l'originale dopo il salvataggio`: salva la copia firmata nella cartella
  scelta, quindi elimina l'originale senza passare dal Cestino.

La sovrascrittura e l'eliminazione rimuovono la versione originale. Avvengono
solo dopo la firma e i controlli sul file temporaneo. Se il sorgente risulta
cambiato durante la firma, l'operazione viene fermata per quel documento.
Se una copia di destinazione esiste già (anche per nomi uguali provenienti da
cartelle diverse), il documento viene saltato e il suo originale conservato.
Se fallisce solo l'eliminazione, il risultato segnala l'errore e mostra il
percorso della copia firmata già salvata.

Un output viene pubblicato con il nome definitivo solo dopo che il programma ha
verificato la presenza di una nuova firma e la sua integrità crittografica.
Questo controllo non certifica da solo la validità legale o la catena di fiducia
del certificato.

## Aggiungere una seconda firma allo stesso PDF

1. Premere `Aggiungi PDF…`.
2. Selezionare il precedente file `_firmato.pdf`.
3. Scegliere un altro angolo per non sovrapporre i riquadri visibili.
4. Avviare una nuova firma.

La prima firma viene preservata grazie all'aggiornamento incrementale del PDF.
Il nuovo nome avrà un altro suffisso, per esempio
`documento_firmato_firmato.pdf`.

## Annullamento

Durante il batch premere `Annulla dopo il file corrente`. L'operazione già
consegnata al middleware non viene interrotta bruscamente. I file successivi
risultano annullati e quelli completati restano validi.


## Schermata documenti e posizionamento

La schermata principale mostra il percorso della cartella in uso, senza i
precedenti riquadri di stato. Gli avvisi compaiono vicino all'elenco soltanto
quando necessario. La selezione evidenzia tutta la riga; le caselle indicano
i PDF inclusi nella firma. `Seleziona tutti` seleziona o deseleziona i risultati
attualmente visibili, rispettando ricerca e sottocartella. Il pulsante
`Prepara la firma` mostra il totale dei documenti spuntati, anche se alcuni
sono nascosti da un filtro.

Il riquadro completo misura circa 75 × 32 mm, con l'altezza precedente invariata.
I quattro preset lo collocano a circa 3 mm dai bordi. Il trascinamento permette
di raggiungere il bordo effettivo del foglio, senza uscire dalla pagina.
Le coordinate restano coerenti cambiando zoom e vengono usate nel PDF firmato.
L'aggiornamento modifica i precedenti valori standard; dimensioni e margini
personalizzati sono conservati.

## Registro persistente delle firme

Oltre alla cronologia degli ultimi 100 lotti, ogni documento viene registrato
nel file `signatures.jsonl` accanto alla configurazione. La pagina Cronologia
mostra il percorso e permette di aprirne la cartella.

Il registro include un campo dedicato al nome del firmatario, tessera,
certificato, file originale e firmato, date UTC, esito, impronta SHA-256 del PDF
firmato e identificativi univoci di operazione, lotto e postazione.
La registrazione avviene durante la firma, dopo ciascun documento.
Un problema di scrittura viene segnalato e impedisce di proseguire con altre
firme; i PDF già salvati vengono conservati.

Per struttura, conservazione e futuro database esterno, consultare
[Registro delle firme](REGISTRO_FIRME.md).
