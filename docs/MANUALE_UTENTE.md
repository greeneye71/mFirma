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

## Configurazione iniziale

Nella parte superiore della finestra compilare:

| Campo | Significato |
|---|---|
| Cartella da firmare | Radice che contiene una sottocartella per ogni persona |
| DLL PKCS#11 | Libreria installata dal middleware; usare `Rileva…` o `Sfoglia…` |
| Token | Etichetta del token; può restare vuota se è presente un solo token |
| Certificato | Etichetta del certificato di firma; è obbligatoria |
| Chiave | Etichetta della chiave privata, solo se diversa dal certificato |
| Posizione | Angolo della pagina in cui mostrare il riquadro firma |

La configurazione viene salvata quando si avvia una firma. Il PIN non fa parte
della configurazione.

### Rilevare automaticamente la DLL

Premere `Rileva…` accanto a `DLL PKCS#11`. mFirma cerca candidate nelle cartelle
dei programmi installati e nelle posizioni standard di Windows, accetta
soltanto DLL x64 e verifica l'interfaccia PKCS#11 in un processo separato. Il
controllo non richiede il PIN e può durare alcuni secondi.

La finestra mostra percorso, eventuali token collegati e origine della
candidata. Selezionare una riga e premere `Usa selezionata`, oppure fare doppio
clic. Quando viene rilevata una sola etichetta di token o certificato e il campo
corrispondente è vuoto, viene compilato automaticamente.

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
