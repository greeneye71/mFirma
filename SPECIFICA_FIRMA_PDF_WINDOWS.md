# Specifica tecnica per applicazione Windows di firma PDF

> Documento di progetto e prompt operativo per Codex o Claude Code
>
> Stato: base di sviluppo da validare sui dispositivi reali
>
> Piattaforma obiettivo: Windows 11 64 bit
>
> Linguaggio principale: Python

## 1. Scopo del documento

Questo documento descrive un'applicazione desktop per Windows 11 che semplifica la firma digitale di molti file PDF mediante smart card o token USB. L'applicazione resta disponibile nell'area di notifica di Windows, può ricevere file selezionati da Esplora file e controlla una directory di rete organizzata in sottocartelle per persona.

Il documento ha due usi:

1. specifica funzionale e tecnica comprensibile anche a chi non sviluppa abitualmente software;
2. base di lavoro da fornire a Codex o Claude Code per costruire il progetto per passi verificabili.

La priorità è realizzare una prima versione semplice, sicura e collaudabile. La compatibilità effettiva con una smart card o un token non deve essere data per scontata: dipende dal modello del dispositivo, dal middleware installato, dall'architettura a 32 o 64 bit, dai certificati presenti e dai meccanismi di firma supportati.

## 2. Risultato atteso

L'utente deve poter:

- vedere dall'icona nella system tray quanti PDF sono in attesa;
- aprire una dashboard con il totale e il conteggio per persona;
- selezionare uno o molti PDF in Esplora file e scegliere un comando di firma;
- selezionare dalla dashboard tutti i documenti o solo una parte;
- scegliere un certificato di firma disponibile sul dispositivo;
- confermare la posizione visibile della firma usando un preset semplice;
- inserire il PIN al momento della firma, senza che il programma lo salvi;
- firmare un batch continuando, quando possibile, anche se un singolo file genera un errore;
- trovare i PDF firmati nella stessa cartella oppure in una destinazione separata;
- consultare un riepilogo finale chiaro e un registro tecnico privo di dati segreti.

Il programma non firma automaticamente i documenti solo perché compaiono nella cartella. Il monitoraggio aggiorna la coda e i conteggi; l'avvio della firma richiede sempre un'azione esplicita dell'utente.

## 3. Glossario essenziale

| Termine | Significato in questo progetto |
|---|---|
| Smart card o token | Dispositivo che contiene il certificato e la chiave privata. La chiave privata non deve essere esportata dal dispositivo. |
| Middleware | Software e driver del produttore che permettono a Windows e alle applicazioni di usare il dispositivo. |
| PKCS#11 | Interfaccia standard, normalmente esposta su Windows mediante una DLL, per comunicare con dispositivi crittografici. |
| CSP o CNG | Interfacce crittografiche di Windows. Alcuni dispositivi espongono il certificato tramite CryptoAPI/CSP o CNG invece di PKCS#11, oppure tramite entrambe. |
| PAdES | Firma digitale incorporata nel PDF secondo profili specifici per documenti PDF. |
| Aspetto visibile | Riquadro grafico mostrato su una pagina del PDF. Non è la firma crittografica in sé e non va chiamato semplicemente filigrana. |
| PIN | Codice segreto richiesto dal dispositivo o dal middleware per autorizzare l'uso della chiave privata. |
| Batch | Insieme di più PDF firmati durante una singola operazione avviata dall'utente. |
| Provider di firma | Modulo del programma che nasconde le differenze tra PKCS#11, CSP/CNG o un'eventuale integrazione specifica del produttore. |
| TSA | Servizio di marcatura temporale. Serve per alcuni profili PAdES, ma richiede configurazione e connettività specifiche. |

## 4. Principi non negoziabili

1. **La chiave privata resta nel dispositivo.** L'applicazione invia al provider solo i dati necessari alla firma.
2. **Il PIN non viene mai scritto su disco.** Non deve apparire nella configurazione, nei log, nei messaggi di errore o nei dump prodotti volontariamente dall'applicazione.
3. **Nessuna promessa sul riuso del PIN.** Il programma può tentare di mantenere una sessione aperta per un batch, ma il token o il middleware possono richiedere il PIN di nuovo per ogni documento, chiudere la sessione o mostrare una propria finestra. Il comportamento va provato sul dispositivo reale.
4. **Nessuna sovrascrittura silenziosa.** Un file sorgente o un PDF firmato esistente non viene sostituito senza una regola configurata e una conferma esplicita.
5. **Un errore non annulla il resto del batch.** Ogni file ha un proprio esito, salvo un errore globale come rimozione del token o annullamento dell'utente.
6. **La firma è avviata dall'utente.** Il monitoraggio della rete non deve trasformarsi in firma automatica non presidiata.
7. **Le integrazioni dipendenti dal dispositivo restano isolate.** La logica della coda, dell'interfaccia e dei PDF non deve dipendere da una particolare DLL o marca.
8. **Prima la prova tecnica, poi l'interfaccia completa.** Compatibilità del token, PAdES e menu contestuale devono essere dimostrati con prototipi piccoli prima di costruire tutto il prodotto.

## 5. Ambito della prima versione

### 5.1 Incluso nell'MVP

- applicazione Python per Windows 11 64 bit;
- icona persistente nella system tray;
- finestra dashboard apribile dall'icona;
- scansione periodica di una directory locale o UNC di rete;
- sottocartelle di primo livello usate come nomi delle persone;
- conteggio complessivo e per persona dei PDF da firmare;
- scelta di uno o più file dalla dashboard;
- ricezione di una selezione multipla da Esplora file;
- firma batch con avanzamento e possibilità di annullare i file non ancora iniziati;
- provider PKCS#11, solo dopo una prova riuscita con DLL e dispositivo reali;
- interfaccia astratta per aggiungere un provider CSP/CNG senza modificare il resto dell'applicazione;
- firma PDF PAdES con aspetto visibile;
- preset alto sinistra, alto destra, basso sinistra e basso destra;
- scelta della pagina, con ultima pagina come valore predefinito;
- anteprima prima dell'avvio e modifica eccezionale della posizione per singolo file o batch;
- destinazione nella stessa cartella o sotto una directory separata;
- configurazione persistente senza segreti;
- log rotanti e riepilogo degli errori per file;
- pacchetto installabile e disinstallabile su Windows 11;
- test automatici della logica che non richiede il token e test manuali con il dispositivo reale.

### 5.2 Escluso dall'MVP

- firma completamente automatica o non presidiata;
- memorizzazione del PIN;
- firma di formati diversi dal PDF;
- firma remota o cloud;
- workflow di approvazione multiutente;
- modifica del contenuto dei PDF oltre al campo/aspetto di firma;
- validità legale garantita per ogni contesto normativo;
- supporto dichiarato per qualunque marca di token;
- menu moderno di primo livello di Windows 11 se richiede una shell extension nativa non ancora collaudata;
- PAdES-LT o PAdES-LTA senza requisiti espliciti, TSA, catena di fiducia e accesso alle informazioni di revoca correttamente configurati.

## 6. Struttura della directory monitorata

Struttura prevista:

```text
\\server\ufficio\Da firmare\
├── Mario Rossi\
│   ├── documento_001.pdf
│   ├── documento_002.pdf
│   └── pratica_A\
│       └── allegato.pdf
├── Lucia Bianchi\
│   ├── documento_003.pdf
│   └── documento_004.pdf
└── Giuseppe Verdi\
    └── documento_005.pdf
```

Regole proposte:

- il nome della sottocartella di primo livello identifica la persona;
- la scansione può essere ricorsiva all'interno della cartella della persona;
- vengono considerati solo file con estensione `.pdf`, senza distinzione tra maiuscole e minuscole;
- cartelle temporanee, nascoste e la directory di destinazione dei firmati devono essere escluse;
- i file già firmati dall'applicazione non devono rientrare nella coda;
- un PDF viene mostrato come `in preparazione` finché dimensione e data di modifica non rimangono stabili per un intervallo configurabile;
- file non leggibili, incompleti o bloccati vengono segnalati senza bloccare il monitoraggio;
- se la rete non è disponibile, l'ultima fotografia nota può rimanere visibile ma deve essere marcata chiaramente come non aggiornata.

La deduplicazione non deve basarsi solo sul nome. Per l'MVP si può usare una chiave composta da percorso normalizzato, dimensione e data di modifica. Un hash del contenuto può essere calcolato al momento della firma o quando serve maggiore certezza.

## 7. Flussi utente

### 7.1 Avvio e system tray

1. L'applicazione parte manualmente o all'accesso dell'utente, se l'opzione è abilitata.
2. Compare una sola icona nella system tray.
3. L'icona mostra nel tooltip lo stato sintetico, per esempio `Firma PDF - 37 documenti in attesa`.
4. Un clic o doppio clic apre la dashboard.
5. Il menu dell'icona offre almeno: `Apri dashboard`, `Aggiorna conteggi`, `Firma documenti in attesa`, `Impostazioni`, `Apri log` ed `Esci`.
6. La chiusura della finestra nasconde la dashboard ma non termina il processo. L'uscita reale avviene dal comando `Esci`.

Le notifiche di Windows sono un aiuto, non l'unico posto dove mostrare informazioni importanti: possono essere disattivate dal sistema.

### 7.2 Dashboard

La dashboard mostra:

- stato della directory monitorata: disponibile, non disponibile o scansione in corso;
- ultimo aggiornamento riuscito;
- totale dei PDF in attesa;
- tabella con persona, numero di PDF, eventuali errori e data del file più vecchio;
- elenco filtrabile dei documenti;
- selezione di tutti i documenti, di una persona o di file singoli;
- pulsante principale `Firma selezionati`;
- accesso alla cronologia recente e alle impostazioni.

L'interfaccia deve usare parole comprensibili. I dettagli tecnici completi vanno nel log; a schermo si preferiscono messaggi come `Il dispositivo di firma non è disponibile` con un pulsante per vedere i dettagli.

### 7.3 Firma dalla directory monitorata

1. L'utente seleziona persone o documenti.
2. L'applicazione esegue un controllo preliminare dei file.
3. Mostra un riepilogo: numero di file, destinazione, certificato, preset visibile e pagina.
4. Se l'anteprima è abilitata, mostra un PDF rappresentativo o consente di scorrere i file.
5. L'utente può applicare un'eccezione di posizione a uno o più file.
6. L'utente conferma.
7. Il provider o l'applicazione richiede il PIN secondo il comportamento del middleware.
8. Parte il batch e viene mostrato l'avanzamento.
9. Alla fine compare il riepilogo con riusciti, saltati, annullati ed errori.

### 7.4 Firma da Esplora file

1. L'utente seleziona uno o molti PDF, anche 50 o 100.
2. Sceglie `Firma PDF` dal menu contestuale disponibile.
3. Un piccolo launcher trasmette l'elenco dei percorsi all'applicazione già in esecuzione e termina rapidamente.
4. Se l'applicazione non è attiva, il launcher la avvia e le consegna la richiesta.
5. La dashboard apre il riepilogo del batch; la firma non parte senza conferma.

Il launcher non deve inserire centinaia di percorsi in un'unica fragile riga di comando. La soluzione preferita è un canale locale con accesso limitato all'utente corrente, per esempio una named pipe, oppure un file di richiesta temporaneo con nome imprevedibile e permessi appropriati, seguito da una notifica all'applicazione.

### 7.5 Annullamento

- `Annulla` impedisce di iniziare i file successivi.
- Non si deve interrompere brutalmente una singola operazione crittografica già consegnata al middleware.
- I file già firmati restano validi e sono elencati nel riepilogo.
- I file non iniziati risultano `annullati`, non `errore`.

## 8. Requisiti funzionali

### 8.1 Applicazione e istanza singola

- **FR-APP-001** L'applicazione deve funzionare su Windows 11 64 bit.
- **FR-APP-002** Deve esistere una sola istanza per utente Windows.
- **FR-APP-003** Una seconda invocazione deve inoltrare la richiesta alla prima istanza e poi terminare.
- **FR-APP-004** L'applicazione deve poter essere configurata per partire all'accesso dell'utente.
- **FR-APP-005** L'uscita deve chiudere sessioni del provider e risorse di monitoraggio in modo ordinato.

### 8.2 Monitoraggio e conteggi

- **FR-MON-001** Deve essere configurabile una radice locale o UNC, per esempio `\\server\ufficio\Da firmare`.
- **FR-MON-002** Ogni sottocartella di primo livello rappresenta una persona.
- **FR-MON-003** La scansione deve contare i PDF anche nelle sottocartelle interne, se l'opzione ricorsiva è attiva.
- **FR-MON-004** Il totale deve essere uguale alla somma dei conteggi per persona, al netto di file esclusi o già firmati.
- **FR-MON-005** L'intervallo di aggiornamento deve essere configurabile, con un valore iniziale ragionevole di 30–60 secondi.
- **FR-MON-006** Deve esistere un comando di aggiornamento manuale.
- **FR-MON-007** La perdita della rete non deve chiudere l'applicazione.
- **FR-MON-008** La scansione non deve bloccare l'interfaccia.
- **FR-MON-009** I cambiamenti rapidi devono essere raggruppati per evitare aggiornamenti continui.
- **FR-MON-010** Un file deve essere considerato pronto solo quando è leggibile e stabile.

Su condivisioni di rete non si deve fare affidamento esclusivo sulle notifiche del file system. Per l'MVP è preferibile una scansione periodica robusta; eventuali eventi servono solo ad anticipare una nuova scansione.

### 8.3 Selezione e coda

- **FR-QUE-001** L'utente deve poter selezionare tutti i file, una persona o singoli PDF.
- **FR-QUE-002** La coda deve conservare l'ordine deterministico scelto, per esempio persona, cartella e nome file.
- **FR-QUE-003** Ogni elemento deve avere uno stato: `in attesa`, `controllo`, `firma`, `riuscito`, `saltato`, `errore` o `annullato`.
- **FR-QUE-004** Lo stesso percorso non deve essere inserito due volte nello stesso batch.
- **FR-QUE-005** Prima di firmare, percorso, dimensione e data di modifica devono essere ricontrollati.
- **FR-QUE-006** Se il file cambia dopo l'anteprima, deve essere richiesto un nuovo controllo o una nuova conferma.

### 8.4 Provider e certificati

- **FR-PRV-001** L'applicazione deve esporre un'interfaccia comune per i provider di firma.
- **FR-PRV-002** Il provider PKCS#11 deve accettare una DLL configurabile e non codificata nel sorgente.
- **FR-PRV-003** Devono essere elencati solo certificati compatibili con la firma, per quanto determinabile dal provider.
- **FR-PRV-004** La selezione del certificato può essere memorizzata tramite identificatore non segreto, ma va riconfermata se il dispositivo o certificato cambia.
- **FR-PRV-005** Scadenza, soggetto, emittente, numero seriale e uso chiave rilevante devono essere mostrati quando disponibili.
- **FR-PRV-006** L'applicazione deve distinguere `dispositivo assente`, `DLL non caricabile`, `certificato non trovato`, `PIN errato`, `PIN bloccato o quasi bloccato se segnalato`, `operazione annullata` ed `errore di firma`.
- **FR-PRV-007** Non si devono inventare messaggi sul numero di tentativi PIN se il middleware non fornisce quel dato.
- **FR-PRV-008** Un provider CSP/CNG deve poter essere aggiunto senza cambiare la coda, l'interfaccia o il servizio PDF.

### 8.5 PIN e sessione

- **FR-PIN-001** Il PIN non deve essere memorizzato in alcuna configurazione o database.
- **FR-PIN-002** Il campo di inserimento deve essere mascherato e non deve supportare funzioni che lo espongano involontariamente.
- **FR-PIN-003** Il PIN non deve essere incluso in eccezioni, telemetria, log o schermate di diagnostica.
- **FR-PIN-004** L'applicazione deve eliminare i riferimenti al PIN appena possibile, sapendo che Python non può garantire l'azzeramento di tutte le copie in memoria.
- **FR-PIN-005** Se il middleware mostra una propria finestra protetta per il PIN, l'applicazione deve preferire o rispettare quel flusso.
- **FR-PIN-006** L'interfaccia deve spiegare che il numero di richieste PIN durante un batch dipende dal token e dal middleware.
- **FR-PIN-007** Dopo PIN errato, l'applicazione non deve tentare automaticamente più volte.

### 8.6 Firma PDF PAdES

- **FR-PDF-001** L'output deve rimanere un file PDF con firma PAdES incorporata.
- **FR-PDF-002** Per l'MVP il profilo esatto deve essere configurato e validato; il candidato iniziale è PAdES Baseline B-B senza marca temporale esterna.
- **FR-PDF-003** PAdES B-T, LT o LTA richiedono una decisione esplicita e una configurazione verificata di TSA, catena, revoche e rete.
- **FR-PDF-004** Il file firmato deve contenere un campo firma nuovo oppure usare un campo esistente solo secondo una regola esplicita.
- **FR-PDF-005** La firma visibile deve poter essere applicata all'ultima pagina o a una pagina scelta.
- **FR-PDF-006** Devono esistere i quattro preset d'angolo.
- **FR-PDF-007** Margini, larghezza e altezza del riquadro devono essere configurabili entro limiti validi.
- **FR-PDF-008** Il calcolo deve tenere conto di MediaBox, CropBox e rotazione della pagina.
- **FR-PDF-009** Il testo visibile deve essere configurabile senza affermazioni legali non verificate. Possibili campi: nome del firmatario, data e ora, motivo e località.
- **FR-PDF-010** Un logo può essere opzionale, ma non deve nascondere le informazioni essenziali.
- **FR-PDF-011** La firma crittografica deve essere verificata subito dopo la creazione almeno a livello di integrità strutturale e crittografica disponibile.
- **FR-PDF-012** Un PDF cifrato, corrotto, con restrizioni o struttura non supportata deve produrre un errore relativo al solo file.

La semplice presenza del riquadro grafico non dimostra che il documento sia firmato. Il test deve verificare l'oggetto firma PAdES, non soltanto l'aspetto visibile.
La data mostrata nel riquadro è informativa e non equivale a una marca temporale attendibile fornita da una TSA.

### 8.7 Preset e anteprima

- **FR-VIS-001** Il preset predefinito deve essere persistente.
- **FR-VIS-002** L'anteprima deve mostrare pagina e rettangolo della firma senza modificare il sorgente.
- **FR-VIS-003** L'utente deve poter spostare o ridimensionare il rettangolo per un'eccezione.
- **FR-VIS-004** L'eccezione deve essere applicabile al file corrente o all'intero batch, con scelta esplicita.
- **FR-VIS-005** Le coordinate salvate devono essere normalizzate rispetto alla pagina oppure riconvertite in punti PDF in modo documentato.
- **FR-VIS-006** Un rettangolo fuori pagina deve essere impedito prima della firma.
- **FR-VIS-007** Per pagine di dimensioni diverse, il preset deve essere ricalcolato, non copiato come coordinate assolute cieche.

### 8.8 Destinazione e nomi file

Modalità A, stessa cartella:

```text
documento.pdf
documento_firmato.pdf
```

Modalità B, radice separata con struttura relativa preservata:

```text
Sorgente:  \\server\ufficio\Da firmare\Mario Rossi\pratica_A\documento.pdf
Output:    \\server\ufficio\Firmati\Mario Rossi\pratica_A\documento_firmato.pdf
```

- **FR-OUT-001** La modalità deve essere configurabile.
- **FR-OUT-002** Il suffisso predefinito deve essere configurabile, con valore consigliato `_firmato`.
- **FR-OUT-003** L'output separato deve preservare il percorso relativo sotto `Da firmare`.
- **FR-OUT-004** Le directory mancanti devono essere create solo sotto la radice configurata.
- **FR-OUT-005** Prima di scrivere, il percorso finale deve essere normalizzato e verificato per impedire l'uscita dalla radice prevista.
- **FR-OUT-006** La scrittura deve avvenire prima in un file temporaneo nella destinazione e diventare definitiva solo dopo esito positivo.
- **FR-OUT-007** Il sorgente non deve essere eliminato dall'MVP.
- **FR-OUT-008** Se l'output esiste, il comportamento predefinito è `salta e segnala`.
- **FR-OUT-009** Opzioni future possono includere `crea versione numerata` o `sovrascrivi con conferma`, mai come default silenzioso.
- **FR-OUT-010** Un output parziale deve essere rimosso o rinominato come file di errore non confondibile con un PDF firmato.

### 8.9 Avanzamento e riepilogo

- **FR-BAT-001** Devono essere visibili numero totale, indice corrente, nome file e persona.
- **FR-BAT-002** Devono essere mostrati conteggi separati per riusciti, errori, saltati e annullati.
- **FR-BAT-003** La UI deve restare responsiva durante il batch.
- **FR-BAT-004** Il lavoro crittografico deve essere seriale per impostazione predefinita; non si presume che token e middleware supportino firme parallele.
- **FR-BAT-005** Al termine deve essere possibile copiare o esportare un riepilogo senza PIN o dati crittografici sensibili.
- **FR-BAT-006** Un errore relativo a un PDF deve consentire di proseguire.
- **FR-BAT-007** Un errore del provider può sospendere il batch e chiedere all'utente se riprovare, saltare o annullare.

### 8.10 Log e diagnostica

- **FR-LOG-001** I log devono essere rotanti, con dimensione e numero di file limitati.
- **FR-LOG-002** Ogni batch deve avere un identificatore casuale.
- **FR-LOG-003** Ogni riga rilevante deve includere data, livello, componente, batch e file, quando applicabile.
- **FR-LOG-004** Il PIN e altri segreti devono essere filtrati sempre.
- **FR-LOG-005** I percorsi possono contenere dati personali; il livello diagnostico esteso deve essere opzionale e i log vanno conservati per un periodo configurabile.
- **FR-LOG-006** Il log deve distinguere messaggio per l'utente e dettaglio tecnico.
- **FR-LOG-007** Deve esistere un pulsante `Apri cartella log`.
- **FR-LOG-008** Un pacchetto diagnostico futuro deve richiedere conferma e applicare redazione dei dati sensibili.

## 9. Requisiti non funzionali

- **NFR-001 Usabilità:** una firma standard deve richiedere il minor numero ragionevole di scelte dopo la configurazione iniziale.
- **NFR-002 Reattività:** scansione, anteprima e firma non devono bloccare il thread grafico.
- **NFR-003 Robustezza:** indisponibilità di rete o token non deve causare perdita della configurazione o chiusura inattesa.
- **NFR-004 Sicurezza:** principio del minimo privilegio; nessuna esecuzione come amministratore durante l'uso normale.
- **NFR-005 Manutenibilità:** separazione netta tra UI, dominio, file system, PDF e provider crittografico.
- **NFR-006 Tracciabilità:** requisiti, test ed errori devono usare identificatori stabili.
- **NFR-007 Prestazioni:** un elenco di almeno 1.000 PDF deve poter essere contato e filtrato senza rendere inutilizzabile la UI; l'obiettivo preciso va misurato sulla rete reale.
- **NFR-008 Accessibilità:** controllo completo da tastiera, etichette comprensibili e contrasto adeguato.
- **NFR-009 Distribuzione:** installazione e disinstallazione non devono richiedere Python preinstallato.
- **NFR-010 Compatibilità:** architettura di applicazione, Python e middleware devono coincidere, normalmente 64 bit su Windows 11 64 bit.

## 10. Architettura proposta

### 10.1 Vista generale

```text
Esplora file ──> Launcher leggero ──> IPC locale ──┐
                                                   │
Directory di rete ──> Scanner ──> Indice/Coda ─────┤
                                                   v
System tray e dashboard ──> Application Service ──> Batch Orchestrator
                                                     │
                              ┌──────────────────────┼─────────────────────┐
                              v                      v                     v
                         PDF Service          Signing Provider       Output Service
                              │                PKCS11 / CSP-CNG             │
                              └──────────────────────┼─────────────────────┘
                                                     v
                                              PDF PAdES firmato
```

### 10.2 Separazione dei moduli

| Modulo | Responsabilità | Non deve fare |
|---|---|---|
| UI | Tray, dashboard, dialoghi, anteprima e avanzamento | Accedere direttamente a DLL o firmare PDF |
| Application service | Coordina casi d'uso e traduce errori in messaggi | Conoscere dettagli Qt o PKCS#11 |
| Scanner | Legge directory, stabilità file, esclusioni e conteggi | Firmare o spostare file |
| Queue | Mantiene elementi e stati del batch | Mostrare finestre |
| PDF service | Prepara campo/aspetto, PAdES e verifica output | Chiedere direttamente il PIN |
| Signing provider | Scopre dispositivi/certificati e produce firme crittografiche | Decidere percorsi di output o layout UI |
| Output service | Nomi, collisioni e scrittura atomica | Accedere alla chiave privata |
| Repository | Salva configurazione, stato non segreto e cronologia | Salvare il PIN |
| Shell integration | Registra/rimuove il comando e inoltra selezioni | Eseguire firma nel processo di Esplora file |

### 10.3 Modello di dominio minimo

```python
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class JobStatus(StrEnum):
    PENDING = "pending"
    CHECKING = "checking"
    SIGNING = "signing"
    SUCCEEDED = "succeeded"
    SKIPPED = "skipped"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class DocumentCandidate:
    source: Path
    person: str | None
    size: int
    modified_ns: int


@dataclass(frozen=True)
class SignaturePlacement:
    page_index: int
    x1: float
    y1: float
    x2: float
    y2: float


@dataclass
class SignJob:
    job_id: str
    document: DocumentCandidate
    destination: Path
    placement: SignaturePlacement
    status: JobStatus = JobStatus.PENDING
    error_code: str | None = None
```

I tipi definitivi possono differire, ma non devono contenere il PIN e non devono dipendere da Qt.

### 10.4 Astrazione del provider di firma

Interfaccia indicativa:

```python
from collections.abc import Iterable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class CertificateInfo:
    provider_id: str
    certificate_id: str
    subject: str
    issuer: str
    serial_number: str
    valid_from: str
    valid_to: str
    key_algorithm: str | None


@dataclass(frozen=True)
class ProviderCapabilities:
    supports_session_reuse: bool | None
    prompts_pin_itself: bool | None
    supported_digest_algorithms: tuple[str, ...]
    notes: tuple[str, ...] = ()


class SigningSession(Protocol):
    def certificate(self) -> CertificateInfo: ...
    def sign_raw(self, data: bytes, digest_algorithm: str) -> bytes: ...


class SigningProvider(Protocol):
    @property
    def provider_type(self) -> str: ...

    def probe(self) -> ProviderCapabilities: ...
    def list_certificates(self) -> Iterable[CertificateInfo]: ...
    def open_session(
        self,
        certificate_id: str,
        pin: bytearray | None,
    ) -> AbstractContextManager[SigningSession]: ...
```

Indicazioni importanti:

- `supports_session_reuse` è `True`, `False` oppure `None` se non noto;
- l'interfaccia non deve promettere che una sessione eviti nuove richieste PIN;
- alcuni middleware gestiscono il PIN autonomamente, quindi `pin` può essere `None`;
- `sign_raw` è solo un nome illustrativo: il contratto definitivo deve specificare senza ambiguità se riceve dati, digest o `DigestInfo`, per evitare doppio hashing e meccanismi PKCS#11 errati;
- gli errori del provider devono essere convertiti in una tassonomia interna, conservando il dettaglio originale solo nel log tecnico;
- il servizio PDF può usare un adapter compatibile con il concetto di `Signer` della libreria PDF, senza rendere pyHanko una dipendenza di tutta l'applicazione.

### 10.5 Provider PKCS#11

Responsabilità:

- caricare la DLL configurata;
- enumerare slot, token e certificati secondo i criteri disponibili;
- permettere selezione per identificatori stabili, preferibilmente seriale token e ID certificato quando disponibili;
- aprire e chiudere la sessione;
- usare la chiave privata senza esportarla;
- mappare meccanismi e algoritmi realmente supportati;
- segnalare con chiarezza incompatibilità 32/64 bit.

pyHanko è un candidato perché documenta firme PDF, profili PAdES, firme visibili e un'integrazione PKCS#11. La sua adozione deve essere confermata da uno spike con il token reale e non implica automaticamente supporto CSP/CNG.

### 10.6 Provider CSP/CNG

Questo provider è una decisione ancora aperta. Possibili strade, da valutare senza mescolarle:

1. usare le API Win32 CryptoAPI/CNG per individuare il certificato e invocare la chiave privata;
2. creare un piccolo bridge nativo, se l'accesso affidabile da Python è insufficiente;
3. usare un SDK o comando del produttore solo se documentato, licenziato e adatto all'uso batch;
4. non implementarlo nell'MVP se il dispositivo reale funziona correttamente via PKCS#11.

Non si deve affermare che pyHanko supporti direttamente CSP/CNG senza un adapter: il suo supporto documentato è PKCS#11. L'eventuale provider Windows dovrà esporre a `PDF Service` la stessa operazione di firma grezza o un adapter equivalente.

### 10.7 Servizio PDF

Responsabilità consigliate:

- aprire il PDF in sola lettura;
- controllare cifratura, struttura, pagine e campi firma esistenti;
- calcolare il riquadro visibile dal preset;
- creare un nome univoco per il campo firma;
- preparare la firma PAdES senza modificare il sorgente;
- delegare la firma crittografica al provider;
- scrivere su stream o file temporaneo;
- riaprire il risultato e verificare la presenza e integrità della nuova firma;
- restituire un esito strutturato.

La selezione di algoritmo e profilo non va codificata in modo arbitrario. Deve risultare dall'intersezione tra requisiti PAdES, certificato, provider e policy concordata.

### 10.8 Monitoraggio della rete

Proposta per l'MVP:

- scansione completa iniziale in un worker;
- nuove scansioni periodiche;
- cache leggera degli attributi dei file;
- confronto tra fotografie successive;
- debounce degli aggiornamenti UI;
- timeout ragionevoli per non lasciare un worker bloccato indefinitamente;
- annullamento della scansione durante la chiusura;
- esclusione esplicita della destinazione firmati.

Un observer basato sugli eventi di Windows può essere aggiunto come ottimizzazione, ma su share UNC, NAS e configurazioni SMB diverse gli eventi possono essere incompleti o tardivi. La scansione periodica resta la fonte di verità.

### 10.9 Stato persistente

Proposta:

- file TOML o JSON per configurazione non segreta;
- database SQLite locale per cronologia batch, deduplicazione e ultima fotografia utile;
- log testuali o JSON Lines rotanti;
- tutto sotto `%LOCALAPPDATA%\NomeApplicazione\` per utente;
- nessun file applicativo scritto nella directory di installazione.

SQLite deve essere usato da un solo componente repository o con accesso serializzato. Non va collocato sulla share di rete.

## 11. Interfaccia grafica proposta

Toolkit raccomandato: **PySide6**, da confermare con il packaging. Offre componenti desktop maturi, system tray, modelli tabellari e possibilità di eseguire worker senza bloccare l'interfaccia.

Finestre minime:

1. **Dashboard** con stato, conteggi e tabella.
2. **Riepilogo batch** con file selezionati e destinazione.
3. **Selezione certificato** con dettagli leggibili.
4. **PIN**, solo se non gestito dal middleware.
5. **Anteprima firma** con preset e rettangolo trascinabile.
6. **Avanzamento** con annullamento controllato.
7. **Esito finale** con filtro sugli errori.
8. **Impostazioni** divise in cartelle, firma, aspetto, provider, log e avvio.

La dashboard può usare un modello tabellare virtualizzato, evitando di creare un widget distinto per ognuno dei 1.000 file.

## 12. Integrazione con Esplora file

### 12.1 Vincolo di Windows 11

Il menu contestuale moderno di Windows 11 usa un'estensione `IExplorerCommand` registrata con identità applicativa. La documentazione Microsoft descrive una DLL COM nativa e un pacchetto, o sparse package, per apparire direttamente nel menu moderno. Questo non è un componente da implementare alla cieca in puro Python.

### 12.2 Strategia in due fasi

**MVP:** registrare un verbo Win32 semplice per i PDF, disponibile se necessario sotto `Mostra altre opzioni`, purché la prova confermi la selezione multipla e la corretta gestione di percorsi con spazi, caratteri Unicode e un numero elevato di file.

**Evoluzione:** implementare una piccola shell extension nativa `IExplorerCommand`, firmata e pacchettizzata, che inoltra i percorsi al launcher senza caricare Python o il motore di firma dentro Esplora file.

In entrambi i casi:

- il comando deve essere visibile solo per PDF o filtrare con messaggio chiaro;
- Esplora file non deve attendere la firma;
- la shell integration non deve caricare la DLL PKCS#11;
- installazione e disinstallazione devono registrare e rimuovere le chiavi/estensioni in modo simmetrico;
- preferire installazione per utente per l'MVP quando possibile;
- la selezione multipla deve essere provata su Windows 11 reale prima di dichiarare completato il requisito.

## 13. Configurazione persistente

Esempio indicativo, senza PIN:

```toml
config_version = 1
language = "it"
start_with_windows = true

[monitor]
root = "\\\\server\\ufficio\\Da firmare"
recursive_within_person = true
scan_interval_seconds = 45
stability_seconds = 5
excluded_directory_names = ["Firmati", ".temp"]

[output]
mode = "separate_root" # "same_directory" oppure "separate_root"
separate_root = "\\\\server\\ufficio\\Firmati"
suffix = "_firmato"
on_collision = "skip"
preserve_relative_tree = true

[signature]
pades_profile = "B-B"
page = "last"
preset = "bottom_right"
margin_points = 24
width_points = 180
height_points = 60
reason = ""
location = ""
show_signer_name = true
show_signing_time = true

[provider]
type = "pkcs11"
module_path = "C:\\Program Files\\Vendor\\middleware-pkcs11.dll"
token_serial = ""
certificate_id = ""

[logging]
level = "INFO"
retention_days = 30
max_file_mb = 5
backup_count = 5
include_full_paths = true
```

Regole:

- validare la configurazione all'avvio e prima di salvarla;
- usare una versione dello schema per future migrazioni;
- scrivere in modo atomico;
- non accettare percorsi di output contenuti dentro sorgenti in modo da creare cicli, salvo esclusioni dimostrate;
- non inserire mai `pin`, `password`, chiavi private o token di servizi nel file;
- per una futura TSA, le credenziali vanno gestite separatamente tramite strumenti sicuri di Windows, non in chiaro nel TOML.

## 14. Struttura proposta del repository

```text
firma-pdf-windows/
├── README.md
├── pyproject.toml
├── uv.lock                         # oppure altro lockfile scelto
├── LICENSE
├── CHANGELOG.md
├── docs/
│   ├── architecture.md
│   ├── device-compatibility.md
│   ├── manual-test-plan.md
│   └── decisions/
│       ├── 0001-ui-toolkit.md
│       ├── 0002-pdf-library.md
│       └── 0003-shell-integration.md
├── src/
│   └── firma_pdf/
│       ├── __init__.py
│       ├── __main__.py
│       ├── bootstrap.py
│       ├── domain/
│       │   ├── models.py
│       │   ├── errors.py
│       │   ├── events.py
│       │   └── policies.py
│       ├── application/
│       │   ├── services.py
│       │   ├── batch_orchestrator.py
│       │   ├── commands.py
│       │   └── dto.py
│       ├── ui/
│       │   ├── tray.py
│       │   ├── dashboard.py
│       │   ├── settings_dialog.py
│       │   ├── certificate_dialog.py
│       │   ├── pin_dialog.py
│       │   ├── preview_dialog.py
│       │   ├── progress_dialog.py
│       │   ├── models/
│       │   └── resources/
│       ├── monitoring/
│       │   ├── scanner.py
│       │   ├── snapshot.py
│       │   ├── stability.py
│       │   └── exclusions.py
│       ├── queue/
│       │   ├── job_queue.py
│       │   └── state_machine.py
│       ├── pdf/
│       │   ├── service.py
│       │   ├── placement.py
│       │   ├── appearance.py
│       │   ├── pades.py
│       │   └── validation.py
│       ├── providers/
│       │   ├── base.py
│       │   ├── registry.py
│       │   ├── pkcs11/
│       │   │   ├── provider.py
│       │   │   ├── session.py
│       │   │   └── error_mapping.py
│       │   └── windows_csp_cng/
│       │       ├── provider.py       # inizialmente stub esplicito
│       │       └── README.md
│       ├── storage/
│       │   ├── config_repository.py
│       │   ├── history_repository.py
│       │   ├── migrations.py
│       │   └── paths.py
│       ├── output/
│       │   ├── naming.py
│       │   └── atomic_writer.py
│       ├── ipc/
│       │   ├── single_instance.py
│       │   ├── server.py
│       │   ├── client.py
│       │   └── protocol.py
│       ├── shell/
│       │   ├── launcher.py
│       │   └── registration.py
│       └── diagnostics/
│           ├── logging_setup.py
│           ├── redaction.py
│           └── health_check.py
├── native/
│   └── explorer_command/             # solo fase menu moderno
├── packaging/
│   ├── pyinstaller/
│   │   └── firma_pdf.spec
│   ├── installer/
│   └── assets/
├── scripts/
│   ├── probe_pkcs11.py
│   ├── sign_one_pdf.py
│   ├── verify_signed_pdf.py
│   └── inspect_environment.py
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── fixtures/
│   │   └── pdf/
│   ├── fakes/
│   │   └── fake_signing_provider.py
│   └── manual/
└── .github/
    └── workflows/
```

Il provider CSP/CNG può restare uno stub che restituisce `non implementato` finché non viene scelta e provata una strategia. Non creare un'implementazione simulata presentandola come funzionante.

## 15. Dipendenze candidate

Le versioni devono essere bloccate nel lockfile dopo le prove. Non fissare qui numeri destinati a diventare obsoleti.

| Funzione | Candidato | Decisione richiesta |
|---|---|---|
| Interfaccia e tray | PySide6 | Confermare dimensione pacchetto, licenza applicabile e packaging. |
| Firma e validazione PDF | pyHanko | Confermare profilo PAdES, aspetto visibile e token reale. |
| Accesso PKCS#11 | integrazione pyHanko/python-pkcs11 | Confermare DLL, slot, certificato, algoritmo e sessione. |
| PDF per anteprima | renderer Qt PDF o componente separato | Scegliere evitando di alterare il PDF. |
| Monitoraggio | scansione con libreria standard; watchdog solo come acceleratore | Non dipendere dagli eventi UNC. |
| Configurazione | TOML/JSON con validazione esplicita | Scegliere una sola libreria/schema. |
| Packaging | PyInstaller in modalità one-folder iniziale | Provare raccolta di plugin Qt e DLL necessarie. |
| Installer | Inno Setup, WiX o MSIX/sparse package | La scelta dipende dal menu contestuale e dalle policy aziendali. |
| Test | pytest e strumenti Qt compatibili | I test con token restano separati e marcati. |

Preferire inizialmente un pacchetto **one-folder**: è più semplice ispezionare DLL, plugin Qt e problemi antivirus rispetto a un unico eseguibile autoestraente. Una distribuzione one-file può essere valutata in seguito.

## 16. Sicurezza

### 16.1 Gestione dei segreti

- non salvare il PIN;
- acquisirlo il più tardi possibile;
- mantenerlo per il minor tempo possibile;
- non convertirlo inutilmente in più stringhe immutabili;
- non inserirlo nei parametri della riga di comando;
- non copiarlo negli appunti;
- non includerlo nei report;
- disabilitare log verbosi delle librerie se possono esporre dati sensibili;
- documentare onestamente che in Python l'azzeramento completo della memoria non è garantibile.

### 16.2 File system

- normalizzare e validare tutti i percorsi;
- usare percorsi assoluti;
- impedire path traversal quando si preserva l'albero relativo;
- non seguire automaticamente link o reparse point fuori dalla radice configurata;
- scrivere prima in un temporaneo e finalizzare solo dopo controllo;
- non cancellare i sorgenti nell'MVP;
- applicare permessi coerenti con quelli della directory di destinazione;
- gestire la possibilità che il file cambi tra scansione e firma.

### 16.3 IPC e istanza singola

- limitare il canale all'utente Windows corrente;
- validare tipo, quantità e dimensione dei messaggi;
- accettare solo percorsi locali o UNC validi secondo la policy;
- non accettare comandi arbitrari;
- usare un protocollo versionato;
- mettere un limite configurabile al numero di file per richiesta, mostrando un errore chiaro invece di esaurire memoria.

### 16.4 Supply chain e distribuzione

- bloccare le versioni delle dipendenze;
- conservare hash o meccanismi di verifica del lockfile;
- eseguire scansione delle dipendenze in CI;
- generare il pacchetto su un ambiente pulito e riproducibile;
- firmare digitalmente installer ed eseguibili con un certificato di code signing, se disponibile;
- non includere DLL del middleware del produttore senza verificarne licenza e modalità di redistribuzione;
- preferire che il middleware venga installato con il pacchetto ufficiale del produttore.

## 17. Packaging e installazione su Windows 11

### 17.1 Artefatti

- `FirmaPdf.exe`: applicazione tray e dashboard;
- `FirmaPdfLauncher.exe`: inoltro rapido dal menu contestuale;
- dipendenze Python e plugin Qt;
- risorse grafiche;
- installer;
- eventuale componente nativo del menu moderno, solo nella fase dedicata.

### 17.2 Installazione

L'installer deve:

1. installare per utente o per macchina secondo la decisione aziendale;
2. non installare silenziosamente middleware di terze parti;
3. creare collegamenti necessari;
4. registrare il comando contestuale scelto;
5. offrire l'avvio all'accesso come opzione modificabile;
6. creare le directory locali dell'applicazione al primo avvio, non con permessi eccessivi;
7. registrare una disinstallazione completa;
8. preservare o rimuovere configurazione e log secondo una scelta esplicita durante la disinstallazione.

### 17.3 Avvio automatico

Per l'MVP scegliere un metodo per utente semplice e reversibile, per esempio collegamento nella cartella Startup o attività pianificata all'accesso senza privilegi elevati. Documentare il metodo e rimuoverlo alla disinstallazione. Non usare un servizio Windows: la firma richiede sessione interattiva, UI e PIN.

### 17.4 Compatibilità di architettura

Costruire normalmente x64. Prima del rilascio verificare:

- architettura della DLL PKCS#11;
- architettura del processo Python impacchettato;
- architettura di eventuale shell extension;
- presenza del runtime richiesto dal componente nativo;
- driver e middleware ufficiali aggiornati per il modello di token.

## 18. Decisioni tecniche da verificare sui dispositivi reali

Questa sezione è obbligatoria: nessuna voce può essere chiusa basandosi solo sulla documentazione generale.

| ID | Decisione o domanda | Prova richiesta | Esito da registrare |
|---|---|---|---|
| DV-001 | Marca, modello e versione firmware del token | Inventario del dispositivo | Valori esatti e PC di prova |
| DV-002 | Middleware e versione installata | Pannello programmi e file DLL | Produttore, versione e percorso |
| DV-003 | Interfaccia disponibile | Probe PKCS#11 e verifica certificati Windows | PKCS#11, CSP, CNG o combinazione |
| DV-004 | Architettura della DLL | Ispezione binario e caricamento da processo x64 | x86/x64 e compatibilità |
| DV-005 | Enumerazione certificato | Elenco slot/token/certificati senza firma | Identificatori stabili disponibili |
| DV-006 | Algoritmi e meccanismi | Firma di dati e PDF di prova | RSA/ECDSA, SHA-256, eventuali vincoli |
| DV-007 | Modalità PIN | Prove con PIN corretto, errato e annulla | Dialogo app o middleware, codici errore |
| DV-008 | Riuso sessione/PIN | Batch controllato di almeno 10 PDF | Numero reale di richieste PIN |
| DV-009 | Rimozione token | Rimuovere il dispositivo tra due file | Errore restituito e recuperabilità |
| DV-010 | PAdES richiesto | Validazione con strumenti concordati | Profilo B-B/B-T/LT/LTA |
| DV-011 | TSA e revoche | Test di rete, trust e indisponibilità | URL, autenticazione, proxy, policy |
| DV-012 | Aspetto visibile | PDF A4, Letter, landscape, ruotato | Coordinate e resa corretta |
| DV-013 | PDF reali | Campione anonimizzato rappresentativo | Cifrati, moduli, firme preesistenti |
| DV-014 | Share di rete | Scansione durante copie e disconnessioni | Stabilità, timeout e prestazioni |
| DV-015 | Menu contestuale | 1, 50 e 100 file con nomi complessi | Visibilità e consegna completa |
| DV-016 | Policy aziendali | Test su PC gestito | Antivirus, AppLocker/WDAC, proxy, installer |

Ogni prova deve produrre una breve scheda in `docs/device-compatibility.md`, senza riportare PIN o dati personali non necessari.

## 19. Spike tecnici obbligatori

### Spike A - un PDF firmato con il token reale

Obiettivo: dimostrare la catena minima prima della GUI.

Passi:

1. caricare la DLL senza crash;
2. elencare token e certificato;
3. firmare un PDF di test non sensibile;
4. creare l'aspetto visibile in una posizione nota;
5. verificare la firma con almeno la libreria usata e un visualizzatore concordato;
6. ripetere su 10 file;
7. registrare quante volte viene chiesto il PIN;
8. provare annullamento e PIN errato una sola volta, evitando rischi di blocco del token.

Criterio di uscita: file PAdES verificabile, comportamento PIN documentato e nessun PIN nei log.

### Spike B - monitoraggio share

Obiettivo: misurare la scansione reale.

Passi:

1. creare almeno 1.000 PDF fittizi in più cartelle;
2. misurare prima scansione e scansioni successive;
3. copiare lentamente un file e verificare lo stato `in preparazione`;
4. interrompere la rete e ripristinarla;
5. verificare che la UI resti reattiva.

### Spike C - selezione multipla da Esplora file

Obiettivo: provare il percorso più semplice accettabile per l'MVP.

Passi:

1. installare la registrazione in ambiente di test;
2. provare un file;
3. provare 50 e 100 file;
4. includere spazi, accenti, parentesi e percorsi UNC;
5. verificare che il launcher termini rapidamente;
6. verificare che ogni percorso arrivi una sola volta;
7. decidere se `Mostra altre opzioni` è accettabile per l'MVP.

### Spike D - provider CSP/CNG, solo se necessario

Obiettivo: decidere fattibilità e costo.

Non iniziare questo spike se PKCS#11 soddisfa il dispositivo e non esiste un requisito aggiuntivo. Il risultato può legittimamente essere `rinviato` o `non fattibile nell'MVP`.

## 20. Gestione degli errori

Tassonomia proposta:

| Codice | Categoria | Comportamento |
|---|---|---|
| `FILE_NOT_FOUND` | File | Segna errore e continua |
| `FILE_CHANGED` | File | Richiede nuova conferma o salta |
| `FILE_LOCKED` | File | Salta con possibilità di riprovare |
| `PDF_INVALID` | PDF | Segna errore e continua |
| `PDF_ENCRYPTED` | PDF | Segna non supportato o richiede policy |
| `OUTPUT_EXISTS` | Output | Salta per default |
| `OUTPUT_WRITE_FAILED` | Output/rete | Segna errore; valuta pausa se sistemico |
| `NETWORK_UNAVAILABLE` | Rete | Mantiene app attiva e ritenta scansione |
| `TOKEN_NOT_PRESENT` | Provider | Sospende batch e chiede azione |
| `MODULE_LOAD_FAILED` | Provider/config | Blocca firma, non il monitoraggio |
| `CERTIFICATE_NOT_FOUND` | Provider | Richiede nuova selezione |
| `PIN_CANCELLED` | Utente | Annulla o sospende senza indicare errore PIN |
| `PIN_INCORRECT` | Provider | Nessun nuovo tentativo automatico |
| `PIN_LOCKED` | Provider | Mostra solo se il middleware lo conferma |
| `SIGNATURE_FAILED` | Provider/PDF | Registra dettaglio e decide se continuare |
| `SIGNED_OUTPUT_INVALID` | Verifica | Non pubblica l'output come riuscito |

Ogni eccezione tecnica deve essere tradotta in uno di questi codici o in un codice più specifico documentato. Evitare `except Exception: pass`.

## 21. Criteri di accettazione dell'MVP

### 21.1 Tray e dashboard

- **AC-001** Su Windows 11 l'app parte e mostra una sola icona nella tray.
- **AC-002** Chiudendo la dashboard, l'app resta attiva; usando `Esci`, termina.
- **AC-003** Con una struttura nota, totale e conteggi per persona sono corretti.
- **AC-004** Con rete scollegata, la dashboard mostra lo stato non disponibile e non si chiude.

### 21.2 Selezione e batch

- **AC-005** Si possono selezionare tutti i file di una persona e file singoli.
- **AC-006** Una selezione di 100 PDF da Esplora file arriva completa e senza duplicati su un PC di test.
- **AC-007** La firma non parte senza conferma esplicita.
- **AC-008** Durante un batch la UI mostra avanzamento e resta utilizzabile.
- **AC-009** Un PDF corrotto produce un errore per quel file e il batch prosegue.
- **AC-010** Annullando, i file già completati restano riusciti e gli altri risultano annullati.

### 21.3 Firma e sicurezza

- **AC-011** Almeno un PDF viene firmato e validato con il token reale concordato.
- **AC-012** Un batch di almeno 100 PDF viene completato sul dispositivo reale in ambiente di prova; il numero di richieste PIN è documentato come comportamento del dispositivo, non imposto dalla specifica.
- **AC-013** Il PIN non compare in configurazione, database, riga di comando o log.
- **AC-014** Rimuovendo il token, il programma mostra un errore controllato e non corrompe i file già prodotti.
- **AC-015** Il certificato usato è quello confermato dall'utente.

### 21.4 PDF e output

- **AC-016** I quattro preset risultano interamente dentro la pagina su A4 portrait, A4 landscape e una pagina ruotata.
- **AC-017** L'anteprima corrisponde con tolleranza definita alla posizione nel PDF firmato.
- **AC-018** La modalità stessa cartella produce il suffisso configurato senza modificare il sorgente.
- **AC-019** La modalità separata preserva la struttura relativa per persona.
- **AC-020** Se l'output esiste, l'MVP lo salta e lo segnala senza sovrascriverlo.
- **AC-021** Un output viene dichiarato riuscito solo dopo verifica della nuova firma.

### 21.5 Installazione

- **AC-022** L'app funziona su un PC Windows 11 pulito senza installazione separata di Python.
- **AC-023** Installazione, aggiornamento e disinstallazione non lasciano una voce contestuale non funzionante.
- **AC-024** L'uso normale non richiede privilegi amministrativi.

## 22. Piano di test

### 22.1 Test unitari automatici

- calcolo dei quattro preset su pagine di dimensioni e rotazioni diverse;
- validazione e normalizzazione dei percorsi;
- preservazione dell'albero relativo;
- regole dei nomi file e collisioni;
- esclusione della directory firmati;
- riconoscimento `.pdf` case-insensitive;
- stabilità di dimensione e data modifica;
- deduplicazione della coda;
- transizioni valide e invalide degli stati;
- redazione del PIN e di campi sensibili nei log;
- mapping degli errori provider mediante fake;
- migrazione e validazione configurazione;
- serializzazione sicura del protocollo IPC.

### 22.2 Test di integrazione senza token

Usare un `FakeSigningProvider` deterministico, chiaramente limitato ai test, per verificare:

- orchestrazione di 100 file;
- errori su file scelti;
- annullamento;
- perdita simulata del provider;
- scrittura atomica e pulizia temporanei;
- cronologia SQLite;
- aggiornamento dei modelli UI;
- ricezione IPC da più invocazioni.

Il fake non dimostra compatibilità crittografica e non deve essere incluso o attivabile nella build di produzione.

### 22.3 Test PDF

Creare fixture non sensibili:

- A4 portrait e landscape;
- Letter;
- pagina ruotata 90, 180 e 270 gradi;
- PDF multipagina;
- PDF con CropBox diverso da MediaBox;
- PDF con campo firma vuoto;
- PDF già firmato;
- PDF cifrato;
- PDF corrotto o troncato;
- nome Unicode e percorso lungo nei limiti supportati;
- documento con contenuto vicino ai quattro angoli per valutare l'anteprima.

Per ogni output verificare almeno: apertura, numero pagine invariato, nuova firma presente, integrità crittografica e rettangolo entro pagina.

### 22.4 Test manuali con token

- token inserito prima dell'avvio;
- token inserito dopo l'avvio;
- token rimosso prima del PIN;
- token rimosso tra due file del batch;
- annullamento del dialogo PIN;
- PIN errato una volta, con cautela;
- certificato scaduto o non idoneo, se disponibile in ambiente di test;
- due certificati presenti;
- batch da 1, 10, 50 e 100 PDF;
- PC bloccato o sessione sospesa durante la coda;
- middleware aggiornato rispetto alla versione iniziale.

Non eseguire test ripetuti di PIN errato che possano bloccare il dispositivo.

### 22.5 Test di rete

- UNC disponibile e non disponibile;
- credenziali di rete già presenti e assenti;
- file copiato lentamente;
- file rinominato durante la scansione;
- permesso di lettura senza scrittura;
- permesso di scrittura nella destinazione ma non nel sorgente;
- disconnessione durante la firma;
- collisione creata da un altro processo;
- latenza elevata;
- almeno 1.000 file distribuiti tra molte persone.

### 22.6 Test di installazione

- installazione per utente standard;
- avvio automatico attivo e disattivo;
- aggiornamento mantenendo configurazione;
- disinstallazione;
- voce contestuale dopo installazione, aggiornamento e rimozione;
- controllo antivirus aziendale;
- percorso di installazione con spazi;
- nome utente Windows con caratteri Unicode.

## 23. Sequenza di implementazione raccomandata

### Fase 0 - raccolta dati

- compilare DV-001–DV-016 per quanto disponibile;
- ottenere PDF di test anonimizzati;
- definire profilo PAdES richiesto e politica di output;
- decidere se `Mostra altre opzioni` è accettabile nell'MVP.

### Fase 1 - spike firma

- creare `probe_pkcs11.py`;
- elencare dispositivo e certificato;
- firmare e verificare un PDF;
- provare il batch minimo;
- scrivere la scheda compatibilità.

Non procedere con un provider dichiarato funzionante se questa fase fallisce.

### Fase 2 - nucleo senza GUI completa

- modelli di dominio;
- scanner e coda;
- output naming e scrittura atomica;
- provider astratto e fake;
- PDF placement;
- orchestratore batch;
- test automatici.

### Fase 3 - tray e dashboard

- istanza singola;
- icona tray;
- dashboard e conteggi;
- impostazioni;
- avanzamento ed errori;
- worker e cancellazione controllata.

### Fase 4 - provider reale

- integrare il codice dello spike dietro `SigningProvider`;
- selezione certificato;
- flusso PIN;
- verifica output;
- test manuali device.

### Fase 5 - Esplora file

- launcher;
- IPC;
- registrazione MVP;
- selezione multipla;
- test su Windows 11.

### Fase 6 - packaging e pilot

- build one-folder;
- installer;
- test su PC pulito;
- pilot con pochi utenti;
- raccolta errori;
- decisione sul menu moderno e CSP/CNG.

## 24. Evoluzioni future

- menu contestuale moderno con `IExplorerCommand` nativo;
- provider CSP/CNG validato;
- profili PAdES B-T, LT o LTA con TSA e revoche;
- regole diverse per persona o tipo documento;
- preset personalizzati nominati;
- rilevamento assistito di aree libere nel PDF;
- firma invisibile come opzione;
- firma multipla sullo stesso PDF;
- dashboard storica e statistiche;
- notifiche configurabili per soglie o anzianità dei documenti;
- esportazione CSV del riepilogo;
- aggiornamenti applicativi firmati;
- gestione centralizzata della configurazione senza includere segreti;
- supporto a più directory radice;
- localizzazione in altre lingue;
- test hardware automatizzati su una postazione dedicata.

Le evoluzioni non devono entrare nell'MVP finché non sono soddisfatti i criteri di accettazione principali.

## 25. Prompt operativo per Codex o Claude Code

Il testo seguente può essere usato come istruzione iniziale insieme a questa specifica.

```text
Realizza il progetto descritto in SPECIFICA_FIRMA_PDF_WINDOWS.md procedendo per fasi piccole e verificabili.

Vincoli obbligatori:
- usa Python come linguaggio principale e Windows 11 64 bit come piattaforma obiettivo;
- mantieni separati UI, dominio, scanner, servizio PDF, output e provider crittografico;
- non salvare mai il PIN e non inserirlo nei log, nella configurazione o nella riga di comando;
- non affermare che una sessione o il PIN siano riutilizzabili in un batch: dipende dal token e dal middleware;
- non implementare una firma automatica non presidiata;
- non sovrascrivere sorgenti o output esistenti per default;
- tratta ogni PDF come un job con esito indipendente;
- non caricare il motore Python, la DLL PKCS#11 o il codice di firma nel processo di Esplora file;
- non dichiarare supporto CSP/CNG finché un provider reale non è stato implementato e provato;
- usa un FakeSigningProvider solo nei test e impediscine l'uso nella build di produzione;
- usa scritture atomiche e verifica il PDF firmato prima di dichiarare successo;
- mantieni la UI responsiva e serializza le operazioni sul token per default;
- blocca le versioni delle dipendenze dopo gli spike.

Metodo di lavoro:
1. Leggi l'intera specifica e crea una matrice requisiti -> moduli -> test.
2. Elenca le decisioni ancora aperte senza inventare risposte.
3. Implementa prima gli spike A, B e C come programmi piccoli separati.
4. Chiedi i dati del dispositivo reale necessari allo spike A se non sono disponibili.
5. Dopo ogni fase esegui test e mostra risultati, file modificati e problemi rimasti.
6. Non costruire tutta la GUI prima di aver dimostrato almeno una firma PAdES valida con il provider reale oppure di aver isolato il lavoro usando il fake.
7. Mantieni una documentazione device-compatibility.md con versioni e risultati, senza segreti.
8. Collega ogni test ai codici FR, NFR e AC pertinenti.

Prima consegna richiesta:
- struttura del repository;
- pyproject e lockfile iniziale;
- modelli di dominio;
- interfaccia SigningProvider;
- FakeSigningProvider per test;
- scanner con test;
- calcolo dei preset di firma con test;
- script probe_pkcs11.py che non chiede o registra il PIN durante la sola enumerazione, se il middleware lo consente;
- breve elenco dei dati mancanti per provare il token reale.

Non procedere con assunzioni silenziose. Quando una capacità dipende dal middleware, indica chiaramente: da verificare sul dispositivo reale.
```

## 26. Checklist per dichiarare pronta una release pilota

- [ ] Spike PKCS#11 completato sul token reale.
- [ ] Profilo PAdES concordato e verificato.
- [ ] Comportamento PIN documentato senza promesse di riuso.
- [ ] Nessun PIN o segreto trovato in configurazione, database e log.
- [ ] Conteggi corretti su share reale.
- [ ] File in copia non firmati prematuramente.
- [ ] Batch da 100 file provato oppure limite documentato e accettato.
- [ ] Quattro preset verificati su pagine ruotate e di formati diversi.
- [ ] Collisioni gestite senza sovrascrittura silenziosa.
- [ ] Output verificato dopo la firma.
- [ ] Rimozione token e perdita rete gestite.
- [ ] Selezione multipla da Esplora file provata.
- [ ] Installer provato su PC pulito.
- [ ] Disinstallazione rimuove integrazioni shell.
- [ ] Antivirus e policy aziendali verificate.
- [ ] Manuale breve per utenti preparato.
- [ ] Limiti noti e dispositivi supportati elencati esplicitamente.

## 27. Riferimenti tecnici verificati

Questi riferimenti sostengono le scelte candidate, ma non sostituiscono le prove con hardware e policy reali:

- [pyHanko - firma PDF e PKCS#11](https://docs.pyhanko.eu/en/latest/cli-guide/signing.html)
- [pyHanko - API di firma e profili PAdES](https://docs.pyhanko.eu/en/latest/lib-guide/signing.html)
- [pyHanko - integrazione PKCS#11](https://docs.pyhanko.eu/en/stable/api-docs/pyhanko.sign.html)
- [Qt for Python - QSystemTrayIcon](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QSystemTrayIcon.html)
- [Microsoft - comando nel menu contestuale moderno di Esplora file](https://learn.microsoft.com/en-us/windows/apps/desktop/modernize/integrate-packaged-app-with-file-explorer)
- [Microsoft - principi per la gestione delle password](https://learn.microsoft.com/en-us/windows/win32/secbp/handling-passwords)
- [PyInstaller - documentazione](https://pyinstaller.org/en/stable/)

## 28. Decisione conclusiva

La strada consigliata è un'applicazione Python modulare con PySide6, pyHanko come candidato per PAdES e PKCS#11, scansione periodica della directory di rete, batch seriale e output atomico. La prima attività di sviluppo non è costruire l'intera applicazione: è dimostrare una firma PAdES corretta con il token reale e documentare il comportamento del PIN.

Il supporto CSP/CNG e il menu contestuale moderno di Windows 11 rimangono estensioni tecniche separate finché non vengono validate. Questa separazione riduce il rischio di costruire un'interfaccia completa attorno a un'integrazione hardware non ancora provata.
