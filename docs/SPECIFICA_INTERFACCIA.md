# Specifica di implementazione dell'interfaccia mFirma

> Stato: approvata; passi da 1 a 4 implementati con GUI Qt eseguibile e testata
>
> Destinatario: Codex o altro agente incaricato dell'implementazione
>
> Ambito: sostituzione della GUI Tkinter; il nucleo di firma esistente resta
> separato e non deve essere riscritto senza necessità

## 1. Obiettivo

Realizzare un'applicazione desktop Windows 11 chiara, moderna e utilizzabile
anche da personale non tecnico. Il flusso ordinario deve essere:

1. vedere i documenti disponibili;
2. selezionare persone o singoli PDF;
3. controllare certificato, destinazione e posizione visibile;
4. confermare e inserire il PIN;
5. seguire l'avanzamento;
6. leggere un esito comprensibile per ogni file.

La configurazione tecnica non deve occupare la dashboard. DLL, token,
certificato, suffisso e cartelle appartengono alla pagina `Impostazioni`.

## 2. Decisione tecnologica

Usare:

- **PySide6** come toolkit Qt ufficiale per Python;
- **PySide6-Fluent-Widgets** (`qfluentwidgets`) per finestra, navigazione,
  controlli e stile Fluent di Windows 11;
- `QTableView`, `QAbstractTableModel` e `QSortFilterProxyModel` per l'elenco;
- `QPdfDocument` e `QPdfView` per l'anteprima;
- `QGraphicsItem` o un overlay Qt dedicato per il rettangolo della firma;
- `QSystemTrayIcon` per l'area di notifica;
- `QThreadPool` e `QRunnable`, oppure worker `QObject` spostati in `QThread`,
  per operazioni non bloccanti.

Non mantenere due GUI complete in parallelo. Durante la migrazione `app.py` può
restare come punto d'ingresso compatibile, ma deve delegare alla nuova
applicazione Qt. Tkinter va rimosso quando la nuova interfaccia copre il flusso
attuale e i test di regressione passano.

Le versioni delle dipendenze vanno fissate in `requirements.lock` soltanto dopo
una prova di avvio e packaging su Windows 11 x64.

## 3. Principi obbligatori

1. La firma parte solo dopo una conferma esplicita.
2. Il PIN non viene salvato, registrato nei log o conservato oltre il necessario.
3. Nessun lavoro lento viene eseguito nel thread grafico.
4. Un errore relativo a un PDF non blocca gli altri documenti.
5. L'annullamento agisce tra un file e il successivo; non interrompe brutalmente
   una firma già consegnata al middleware.
6. Gli originali non vengono modificati.
7. Le informazioni tecniche complete restano nei log; la UI usa messaggi
   orientati all'azione.
8. Tutte le funzioni principali devono essere raggiungibili da tastiera.
9. L'interfaccia deve rimanere usabile con ridimensionamento della finestra e
   scaling di Windows al 125%, 150% e 200%.

## 4. Struttura del codice

Struttura consigliata:

```text
src/mfirma/
├── app.py                         # punto d'ingresso compatibile
├── ui/
│   ├── application.py             # QApplication, tema, icone, avvio
│   ├── main_window.py             # MSFluentWindow e navigazione
│   ├── state.py                   # stato UI non persistente
│   ├── controllers/
│   │   ├── queue_controller.py
│   │   ├── signing_controller.py
│   │   └── settings_controller.py
│   ├── models/
│   │   ├── document_table_model.py
│   │   └── document_filter_model.py
│   ├── pages/
│   │   ├── queue_page.py
│   │   ├── preview_page.py
│   │   ├── progress_page.py
│   │   ├── result_page.py
│   │   ├── history_page.py
│   │   └── settings_page.py
│   ├── dialogs/
│   │   ├── pin_dialog.py
│   │   ├── certificate_dialog.py
│   │   └── middleware_dialog.py
│   ├── widgets/
│   │   ├── document_table.py
│   │   ├── signature_overlay.py
│   │   ├── status_item.py
│   │   └── result_summary.py
│   ├── workers/
│   │   ├── scan_worker.py
│   │   ├── discovery_worker.py
│   │   └── signing_worker.py
│   └── resources/
│       ├── icons.qrc
│       └── translations/
└── ...                            # dominio esistente invariato
```

Le pagine non devono importare direttamente `pyhanko`, `pkcs11` o accedere alle
DLL. Devono chiamare controller o servizi applicativi. Scanner, orchestratore,
provider e servizio PDF esistenti restano la fonte del comportamento.

## 5. Stato globale della UI

Definire uno stato esplicito, senza PIN, che contenga almeno:

```python
@dataclass(slots=True)
class UiState:
    documents: list[DocumentCandidate]
    selected_paths: set[Path]
    active_person: str | None
    search_text: str
    scan_state: str
    device_state: str
    selected_certificate: CertificateSummary | None
    active_batch: BatchUiState | None
```

Gli stati di scansione sono:

- `idle`;
- `scanning`;
- `available`;
- `unavailable`;
- `available_with_warnings`.

Gli stati del dispositivo sono:

- `unknown`;
- `detecting`;
- `ready`;
- `missing`;
- `middleware_error`;
- `certificate_missing`.

La UI reagisce agli stati; non deve dedurli dal testo mostrato nelle etichette.

## 6. Finestra principale

### 6.1 Contenitore

Usare `MSFluentWindow` o il contenitore Fluent equivalente disponibile nella
versione adottata.

- titolo: `mFirma`;
- sottotitolo di prodotto: `Firma PDF`;
- dimensione iniziale consigliata: `1180 × 760` pixel logici;
- dimensione minima: `900 × 620` pixel logici;
- ripristinare dimensione e posizione dell'ultima sessione, verificando che la
  finestra rimanga dentro un monitor disponibile;
- rispettare automaticamente tema chiaro/scuro di Windows;
- colore principale iniziale: `#2667D8`;
- carattere: Segoe UI fornito dal sistema.

La chiusura della finestra la nasconde nella tray. L'uscita reale avviene dal
comando `Esci` della tray o da un comando esplicito della pagina impostazioni.

### 6.2 Navigazione

Voci, nell'ordine:

1. `Da firmare`, con conteggio dei PDF pronti;
2. `Cronologia`;
3. `Impostazioni`.

La navigazione deve passare automaticamente alla forma compatta quando la
larghezza non è sufficiente. In forma compatta le icone devono avere tooltip e
nomi accessibili.

Durante un batch la pagina di avanzamento può essere mostrata anche se l'utente
visita un'altra sezione. Deve rimanere disponibile un'indicazione persistente
`Firma in corso` nella navigazione o nella barra superiore.

## 7. Pagina “Da firmare”

### 7.1 Testata

Mostrare:

- titolo `Documenti da firmare`;
- data e ora dell'ultimo aggiornamento riuscito;
- azione secondaria `Aggiungi PDF`;
- azione secondaria `Aggiorna`.

Durante la scansione `Aggiorna` mostra uno stato occupato e non avvia scansioni
concorrenti. `Aggiungi PDF` accetta selezione multipla e può includere PDF già
firmati per una firma successiva.

### 7.2 Stato operativo

Mostrare tre elementi compatti:

1. cartella: raggiungibile/non raggiungibile e numero di PDF;
2. dispositivo: nome del token oppure motivo dell'indisponibilità;
3. certificato: intestatario e validità sintetica.

Questi elementi sono stato operativo, non statistiche decorative. In caso di
problema devono contenere un'azione pertinente, per esempio `Riprova` o
`Configura dispositivo`.

### 7.3 Filtro per persona

Una colonna laterale mostra:

- `Tutti`;
- una riga per ciascuna persona;
- il numero di PDF pronti per ogni persona.

La selezione della persona filtra l'elenco senza cancellare le selezioni già
effettuate in altri gruppi. Su finestre strette il filtro diventa una barra
orizzontale scorrevole o un selettore compatto.

### 7.4 Elenco documenti

Usare `QTableView` con modello dedicato, non `QTableWidget` e non un widget per
ogni riga.

Colonne:

| Colonna | Contenuto | Comportamento |
|---|---|---|
| selezione | checkbox | supporta seleziona tutti i risultati visibili |
| Documento | nome e percorso relativo secondario | larghezza elastica |
| Persona | sottocartella di primo livello | filtrabile |
| In attesa da | durata comprensibile | ordinamento sul timestamp reale |
| Dimensione | KB/MB | allineata a destra |

Requisiti del modello:

- supportare almeno 1.000 righe senza blocchi percepibili;
- conservare la selezione tramite percorso normalizzato, non tramite indice;
- ordinamento deterministico;
- ricerca senza distinzione tra maiuscole/minuscole su nome, persona e percorso;
- tooltip con percorso completo;
- menu contestuale minimo: `Apri cartella`, `Rimuovi dalla selezione`,
  `Anteprima`;
- doppio clic: apre l'anteprima del documento, non avvia la firma.

La ricerca deve essere differita di circa 150–250 ms per evitare un filtro a
ogni singolo evento durante la digitazione rapida.

### 7.5 Barra di selezione

In fondo all'elenco mostrare:

- numero di documenti selezionati;
- sintesi: pagina, posizione e destinazione;
- pulsante principale `Prepara la firma`.

Il pulsante è disabilitato senza selezione. Non chiedere il PIN in questa pagina.

### 7.6 Stati alternativi

- **Nessun documento:** icona discreta, testo `Non ci sono PDF da firmare` e
  azione `Aggiorna`.
- **Cartella non configurata:** testo e azione `Configura cartella`.
- **Rete non disponibile:** mostra l'ultima fotografia nota come non aggiornata;
  non cancellare immediatamente l'elenco.
- **File in preparazione:** indicare quanti file non sono ancora stabili senza
  inserirli tra i selezionabili.
- **Scansione con errori:** mostrare un banner sintetico e un collegamento ai
  dettagli; non usare una finestra modale per ogni file.

## 8. Pagina “Controlla e firma”

Questa pagina si apre con `Prepara la firma`.

### 8.1 Area anteprima

Usare `QPdfDocument` e `QPdfView` in modalità pagina singola. Aprire inizialmente
l'ultima pagina del primo documento selezionato.

Sopra l'anteprima aggiungere controlli compatti per:

- documento precedente/successivo;
- numero pagina;
- zoom adattato alla pagina e zoom manuale;
- ripristino del preset.

Sovrapporre un rettangolo interattivo che rappresenta l'aspetto della firma:

- trascinabile;
- ridimensionabile tramite maniglie;
- sempre confinato nella pagina;
- aggiornato correttamente con zoom, CropBox e rotazione;
- convertito in coordinate normalizzate o punti PDF soltanto dal componente di
  placement, non da valori pixel salvati dalla UI.

L'anteprima non deve modificare il PDF sorgente.
Il contenuto e il rendering del riquadro sono definiti in
[SPECIFICA_ASPETTO_FIRMA.md](SPECIFICA_ASPETTO_FIRMA.md); anteprima e firma reale
devono usare lo stesso renderer.

### 8.2 Pannello laterale

Mostrare:

- numero di documenti;
- certificato selezionato;
- formato `PAdES B-B`;
- modalità di output;
- quattro preset: alto sinistra, alto destra, basso sinistra, basso destra;
- opzione `Applica questa posizione a tutti i documenti`.

Se le pagine hanno geometrie diverse, il preset viene ricalcolato per ciascuna
pagina. Una posizione personalizzata può essere applicata al documento corrente
oppure all'intero batch solo dopo una scelta esplicita.

Azioni:

- `Torna ai documenti` conserva la selezione;
- `Continua e firma` avvia i controlli preliminari e poi apre il flusso PIN.

## 9. Dialogo PIN

Usare un dialogo Fluent modale con:

- titolo `Inserisci il PIN del dispositivo`;
- spiegazione `Il PIN serve solo per questa operazione e non verrà salvato`;
- campo password mascherato;
- `autocomplete` non applicabile in Qt e nessuna funzione “mostra PIN”;
- nota sul fatto che il middleware può richiederlo nuovamente;
- pulsanti `Annulla` e `Firma N documenti`.

Non validare una lunghezza universale: i token hanno policy differenti. Dopo un
PIN errato non effettuare tentativi automatici. Se il middleware gestisce il
proprio dialogo protetto, mostrare una conferma senza campo PIN e lasciare che
sia il middleware a richiederlo.

Il valore deve essere consegnato al controller una sola volta, rimosso dai
riferimenti UI subito dopo e mai inserito in segnali generici, stato globale,
cronologia o eccezioni mostrate.

## 10. Pagina “Firma in corso”

Mostrare:

- totale e numero completato;
- percentuale;
- nome del file corrente;
- persona;
- fase corrente: controllo, firma o verifica;
- conteggi aggiornati per riusciti, saltati ed errori;
- pulsante `Annulla dopo il file corrente`.

Il progresso è determinato dal numero di job, non da un timer. Il worker invia
eventi strutturati alla UI. La pagina non chiude il worker distruggendo la
finestra.

Quando viene richiesto l'annullamento:

1. disabilitare il pulsante;
2. mostrare `Annullamento richiesto`;
3. lasciare terminare il file corrente;
4. marcare come annullati i job non iniziati;
5. aprire normalmente il riepilogo.

## 11. Pagina esito

Mostrare una testata diversa per:

- completamento senza errori;
- completamento con errori o file saltati;
- annullamento controllato;
- errore globale del provider.

Mostrare quattro conteggi: riusciti, errori, saltati e annullati.

La tabella degli esiti contiene:

- documento;
- persona;
- stato;
- nome o percorso dell'output;
- messaggio orientato all'utente per errori e file saltati.

Azioni:

- `Torna ai documenti`;
- `Apri cartella` quando esiste una destinazione comune;
- `Copia riepilogo`;
- `Mostra solo problemi` quando almeno un job non è riuscito;
- `Dettagli tecnici` apre il log pertinente, senza mostrare segreti.

## 12. Cronologia

Mostrare gli ultimi batch con:

- data e ora;
- certificato;
- numero di documenti;
- esito sintetico;
- identificatore batch non prominente ma copiabile nei dettagli.

Se la persistenza della cronologia non è ancora implementata, la pagina può
essere consegnata in una fase successiva. Non simulare dati in produzione.

Il dettaglio di un batch deve poter ricostruire il riepilogo, ma non contenere il
PIN né dati crittografici sensibili.

## 13. Impostazioni

Dividere in sezioni o sottopagine Fluent.

### 13.1 Cartella monitorata

- percorso locale o UNC;
- `Sfoglia`;
- scansione ricorsiva;
- secondi di stabilità;
- intervallo di aggiornamento quando sarà implementato.

### 13.2 Dispositivo di firma

- percorso DLL PKCS#11;
- `Rileva middleware`;
- `Sfoglia`;
- token selezionato;
- certificato selezionato;
- `Leggi card`;
- chiave manuale nelle impostazioni avanzate.

La finestra certificati mostra uso, intestatario, emittente e scadenza. Evidenzia
`Firma documenti` quando `contentCommitment` è disponibile, ma richiede comunque
la conferma dell'utente se esistono più candidati plausibili.

### 13.3 Firma visibile

- preset predefinito;
- pagina predefinita: ultima pagina;
- margine, larghezza e altezza;
- motivo e località opzionali;
- opzione `Mostra sempre l'anteprima`.

### 13.4 Output

- stessa cartella o radice separata;
- suffisso, inizialmente `_firmato`;
- politica collisione iniziale fissa: `salta e segnala`.

### 13.5 Applicazione e diagnostica

- avvio con Windows, quando disponibile;
- comportamento alla chiusura;
- tema di sistema/chiaro/scuro;
- cartella log;
- livello diagnostico esteso con avviso sulla presenza di percorsi personali.

Le modifiche diventano effettive con `Salva impostazioni`. Validare tutti i campi
e portare il focus sul primo errore. Non salvare configurazioni parzialmente
invalide.

## 14. Tray di Windows

Tooltip:

```text
mFirma — 37 documenti da firmare
```

Menu:

1. `Apri mFirma`;
2. `Aggiorna documenti`;
3. `Firma documenti in attesa` — apre la dashboard con tutti selezionati, non
   avvia automaticamente la firma;
4. `Impostazioni`;
5. `Apri cartella log`;
6. separatore;
7. `Esci`.

Durante un batch il tooltip include il progresso. Le notifiche Windows sono
accessorie: ogni informazione importante deve essere recuperabile nella finestra.

## 15. Messaggi ed errori

Usare `InfoBar` non modale per problemi recuperabili. Usare dialoghi modali solo
quando serve una decisione prima di continuare.

Esempi:

| Condizione | Messaggio principale | Azione |
|---|---|---|
| rete assente | `La cartella non è raggiungibile` | `Riprova` |
| token assente | `Il dispositivo di firma non è disponibile` | `Rileva dispositivo` |
| DLL errata | `Il middleware non può essere caricato` | `Scegli un'altra DLL` |
| certificato scaduto | `Il certificato selezionato è scaduto` | `Scegli certificato` |
| output esistente | `Esiste già un file con questo nome` | nessuna; il job è saltato |
| PDF corrotto | `Il PDF non può essere letto` | `Dettagli` |
| sorgente cambiato | `Il documento è cambiato dopo la selezione` | `Ricontrolla` |
| PIN errato | `Il PIN non è stato accettato` | nuovo tentativo solo manuale |

Non mostrare stack trace nella UI. Associare ogni errore a un codice stabile nel
log e, quando utile, nel pannello dettagli.

## 16. Aspetto visivo

- applicare Fluent Design senza riempire la finestra di card;
- usare superfici per stato operativo, anteprima, riepilogo e gruppi impostazioni;
- usare il blu principale solo per selezione e azione primaria;
- verde per riuscito, giallo per avviso, rosso per errore;
- associare sempre colore a testo o icona;
- una sola azione primaria per gruppo;
- icone Fluent o risorse vettoriali coerenti, mai emoji come icone di prodotto;
- altezza riga comoda circa 48–52 pixel logici, con eventuale modalità compatta
  40–44 pixel;
- spaziatura base 4/8/12/16/24/32 pixel logici;
- angoli coerenti con Fluent, senza ombre marcate su ogni elemento.

Il testo della firma dentro il PDF segue regole separate e deve restare leggibile
nel documento stampato.

## 17. Accessibilità e tastiera

- ordine di tabulazione coerente con l'ordine visivo;
- `Ctrl+F`: porta alla ricerca;
- `Ctrl+A`: seleziona tutti i documenti filtrati quando la tabella ha il focus;
- `F5`: aggiorna la cartella;
- `Invio`: apre l'anteprima dalla tabella;
- `Spazio`: seleziona/deseleziona le righe evidenziate;
- `Esc`: chiude solo il dialogo corrente o torna alla pagina precedente;
- nomi accessibili per icone e pulsanti compatti;
- stato e progresso annunciabili tramite API di accessibilità senza notificare
  ogni aggiornamento minimo;
- contrasto verificato nei temi chiaro e scuro;
- focus sempre visibile.

Non affidarsi esclusivamente a hover, colore o trascinamento: i preset devono
consentire di posizionare la firma anche da tastiera.

## 18. Contratti tra UI e nucleo

La UI deve ricevere eventi strutturati. Interfaccia indicativa:

```python
class SigningUiEventType(StrEnum):
    STARTED = "started"
    JOB_STARTED = "job_started"
    JOB_UPDATED = "job_updated"
    JOB_FINISHED = "job_finished"
    CANCEL_REQUESTED = "cancel_requested"
    FINISHED = "finished"
    GLOBAL_ERROR = "global_error"


@dataclass(frozen=True, slots=True)
class SigningUiEvent:
    type: SigningUiEventType
    completed: int
    total: int
    job: SignJob | None = None
    user_message: str = ""
    error_code: str | None = None
```

Il controller traduce le eccezioni di dominio in eventi e messaggi. Il worker non
deve accedere ai widget. I segnali Qt trasportano soltanto oggetti non segreti.

Per la scansione usare un risultato immutabile con documenti, errori e timestamp.
Aggiornare il modello con un reset o una differenza coerente; non modificare il
modello da un thread secondario.

## 19. Sequenza di implementazione per Codex

### Passo 1 — infrastruttura Qt

- aggiungere e bloccare le dipendenze;
- creare `QApplication` e `MSFluentWindow`;
- impostare tema, icona e navigazione;
- mantenere il punto d'ingresso `python -m mfirma`;
- aggiungere uno smoke test che costruisce e chiude la finestra in modalità
  offscreen.

### Passo 2 — dashboard e modello tabellare

- implementare `DocumentTableModel` e filtro;
- collegare lo scanner esistente;
- implementare selezione stabile per percorso;
- aggiungere stati vuoto, scansione, rete assente e warning;
- testare con almeno 1.000 record fittizi.

### Passo 3 — impostazioni e discovery

- migrare tutti i campi Tkinter;
- collegare `ConfigRepository`;
- migrare ricerca DLL e scelta certificato senza cambiare il provider;
- verificare che il PIN non entri mai nella configurazione.

### Passo 4 — anteprima

- integrare `QPdfView`;
- implementare overlay, preset, zoom, rotazione e vincoli pagina;
- riusare `placement.py` per la conversione;
- aggiungere test sulle coordinate separate dai test grafici.

### Passo 5 — firma, progresso ed esito

- collegare `BatchOrchestrator` tramite worker Qt;
- implementare dialogo PIN e cancellazione controllata;
- mostrare eventi e riepilogo per file;
- verificare prosecuzione dopo errore singolo.

### Passo 6 — tray e rifinitura

- aggiungere tray e comportamento di chiusura;
- aggiungere cronologia quando il repository relativo esiste;
- testare scaling, temi, tastiera e packaging;
- rimuovere definitivamente la GUI Tkinter.

Ogni passo deve lasciare l'app avviabile e i test esistenti verdi. Non unire
migrazione grafica e modifiche al formato di firma nello stesso passo.

### Stato implementativo al 05/09/2026

Sono disponibili `MSFluentWindow`, tema di sistema, colore `#2667D8`, Segoe UI,
navigazione, dashboard, `QTableView`, modello astratto, proxy di filtro,
selezione per percorso normalizzato, ricerca differita e scansione tramite
`QThreadPool`. L'avvio predefinito è `python -m mfirma`.

La pagina impostazioni Qt salva tutti i valori correnti tramite
`ConfigRepository`. Discovery e lettura card usano un worker Qt che richiama il
probe isolato esistente; i dialoghi mostrano dati pubblici reali e conservano la
scelta per etichetta e `CKA_ID`.

La pagina `Controlla e firma` usa `QPdfDocument/QPdfView` sull'ultima pagina,
mostra il PDF prodotto dal renderer condiviso, gestisce zoom, preset,
trascinamento e ridimensionamento. Le coordinate persistenti del flusso sono
punti PDF convertiti da `placement.py`, inclusi CropBox e rotazioni.

PIN, firma, avanzamento ed esito sono collegati al `BatchOrchestrator` tramite
worker Qt. Il tray nasconde e ripristina la finestra; `Esci` attende i worker e
richiede l'annullamento della firma dopo il file corrente. La GUI Tkinter è
stata rimossa.

La geometria viene persistita atomicamente in coordinate logiche e vincolata ai
monitor disponibili al ripristino. Sono implementati `Ctrl+F`, `Ctrl+A`, `F5`,
`Spazio`, `Invio` ed `Esc`; controlli principali, navigazione e avanzamento
espongono nomi o descrizioni accessibili. Tema e scaling hanno smoke test
offscreen, mentre contrasto e screen reader restano da validare sulle
postazioni Windows di collaudo.

## 20. Test UI minimi

Test automatici con `pytest-qt` o strumento equivalente:

1. avvio della finestra senza hardware;
2. caricamento documenti nel modello;
3. filtro per persona e testo;
4. selezione di tutti i risultati visibili;
5. pulsante firma disabilitato senza selezione;
6. salvataggio impostazioni valide e rifiuto di quelle invalide;
7. nessun PIN passato a repository o log fittizio;
8. avanzamento da eventi simulati;
9. annullamento tra job;
10. riepilogo con riusciti, saltati, errori e annullati;
11. chiusura finestra che lascia attiva la tray;
12. uscita dalla tray che chiude ordinatamente i worker.

Test manuali Windows 11:

- temi chiaro e scuro;
- scaling 100%, 125%, 150% e 200%;
- risoluzione minima concordata;
- tastiera senza mouse;
- screen reader disponibile nell'ambiente di collaudo;
- 1.000 righe nella dashboard;
- rete scollegata durante una scansione;
- token rimosso tra due firme;
- batch da 1, 10 e 100 PDF;
- anteprima A4 verticale, orizzontale e pagine ruotate.

## 21. Criteri di accettazione dell'interfaccia

La migrazione è completa quando:

- il flusso precedentemente disponibile in Tkinter funziona nella GUI Qt;
- la configurazione tecnica non occupa la dashboard;
- selezione, ricerca e filtro restano fluidi con 1.000 PDF;
- l'anteprima corrisponde alla posizione finale entro la tolleranza definita nei
  test PDF;
- la UI resta responsiva durante scansione, discovery e firma;
- annullamento ed errori producono stati coerenti per ogni file;
- nessun PIN compare in configurazione, log o oggetti di cronologia;
- tray, temi, scaling e tastiera sono verificati su Windows 11;
- `python -m mfirma` avvia la nuova GUI;
- tutti i test di dominio esistenti continuano a passare.

## 22. Fuori ambito della prima migrazione

- modifica del profilo PAdES;
- firma automatica non presidiata;
- provider cloud o firma remota;
- progettazione di un nuovo formato di configurazione senza necessità;
- riscrittura di scanner, output o provider soltanto per adattarli a Qt;
- animazioni decorative che rallentino operazioni o test;
- shell extension moderna di Windows 11, che resta un'attività separata.
