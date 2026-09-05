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

Nella parte superiore della finestra compilare:

| Campo | Significato |
|---|---|
| Cartella da firmare | Radice che contiene una sottocartella per ogni persona |
| DLL PKCS#11 | Libreria installata dal middleware; usare `Rileva…` o `Sfoglia…` |
| Token | Etichetta del token, compilata dalla lettura quando possibile |
| Seriale (hex) | Identificatore pubblico compilato automaticamente; non è modificabile |
| Certificato | Etichetta del certificato di firma; usare `Leggi card…` per sceglierla |
| Chiave | Etichetta della chiave privata, solo se diversa dal certificato |
| Posizione | Angolo della pagina in cui mostrare il riquadro firma |
| Aspetto | `Completo` (240 × 92 pt) oppure `Compatto` (190 × 68 pt) |

Premere `Salva impostazioni` per rendere effettiva la configurazione. Il PIN non
fa parte della configurazione.

L'aspetto completo mostra i dati pubblici essenziali del firmatario, la data e
l'ora del computer con il fuso, il profilo PAdES B-B, SHA-256 e il numero della
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
clic. Quando viene rilevata una sola etichetta di token o certificato e il campo
corrispondente è vuoto, viene compilato automaticamente.

Se sono collegati più token o smart card, mFirma apre prima l'elenco dei
dispositivi con etichetta, seriale, produttore, modello e slot. Scegliere il
dispositivo da usare; il seriale pubblico permette di distinguere anche token
con la stessa etichetta. Solo dopo vengono mostrati i certificati appartenenti
al dispositivo scelto.

Un middleware valido può comparire anche come `nessuno collegato` quando il
token non è inserito. Se la ricerca non trova nulla, usare `Sfoglia…` e indicare
la DLL documentata dal produttore. Dopo la scelta manuale mFirma legge
automaticamente token e certificati pubblici dalla DLL selezionata.

Se viene trovata una sola etichetta di certificato, il campo `Certificato`
viene compilato automaticamente. Anche in presenza di più certificati, mFirma
sceglie automaticamente l'unico che dichiara l'uso `contentCommitment`, tipico
della firma di documenti. Negli altri casi si apre una finestra di scelta che
mostra l'uso rilevato: selezionare il certificato di firma e premere
`Usa certificato`. Questa lettura non richiede il PIN.

mFirma conserva anche l'ID pubblico del certificato e lo usa per trovare la
chiave privata corrispondente. Il campo `Chiave (opz.)` può quindi restare vuoto
anche quando certificato e chiave hanno etichette diverse.

### Leggere i certificati presenti sulla card

Dopo aver scelto la DLL e collegato la smart card o il token, premere
`Leggi card…`. Si apre l'elenco dei certificati pubblici esposti dal dispositivo
con:

- etichetta PKCS#11;
- uso rilevato, con `Firma documenti` in evidenza quando è dichiarato
  `contentCommitment`;
- intestatario ed emittente;
- data di scadenza.

Selezionare la riga corretta e premere `Usa certificato`, oppure fare doppio
clic. Il campo `Certificato` viene aggiornato e l'ID pubblico associato viene
conservato per individuare la chiave privata. La lettura non richiede il PIN e
non accede alla chiave privata.

## Caricare i documenti

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

Per `documento.pdf` viene creato, nella stessa cartella:

```text
documento_firmato.pdf
```

Il sorgente non viene modificato né cancellato. Se il file di destinazione
esiste già, il documento viene saltato senza sovrascriverlo.

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
