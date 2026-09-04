# Specifica dell'aspetto visibile della firma PDF

> Stato: renderer e integrazione PDF implementati; anteprima Qt da implementare
>
> Ambito: contenuto grafico del campo firma, anteprima e generazione vettoriale
>
> Documento collegato: [SPECIFICA_INTERFACCIA.md](SPECIFICA_INTERFACCIA.md)

## 1. Principio fondamentale

Il riquadro visibile aiuta una persona a individuare la firma e a leggere i dati
principali. Non è la firma crittografica e non dimostra da solo validità,
integrità, qualificazione del certificato o presenza di una marca temporale.

Per questo motivo l'aspetto non deve contenere:

- un segno di spunta verde con significato di `firma valida`;
- frasi come `firma verificata`, `certificato valido` o `documento integro`;
- una data presentata come marca temporale attendibile quando non è usata una
  TSA;
- loghi di autorità o schemi di fiducia che non abbiano autorizzato l'uso;
- QR code senza un servizio di verifica reale, stabile e documentato.

La verifica resta compito del lettore PDF e del relativo contesto di fiducia.

## 2. Riferimenti usati

- Adobe distingue l'aspetto dalla firma effettiva e permette di mostrare nome,
  data, luogo, motivo, distinguished name, etichette e grafica. Specifica anche
  che la data visibile è l'ora locale del computer e può differire da una marca
  temporale: <https://www.adobe.com/devnet-docs/acrobatetk/tools/DigSigDC/appearances.html>
- La documentazione DSS della Commissione europea supporta firme visibili con
  testo, immagine, combinazioni dei due, controllo di posizione e dimensioni.
  Raccomanda di preferire testo PDF nativo per nitidezza e ricercabilità:
  <https://ec.europa.eu/digital-building-blocks/DSS/webapp-demo/doc/dss-documentation.html>
- pyHanko permette `TextStampStyle`, font TrueType/OpenType, sfondi, parametri
  di testo personalizzati e aspetti importati da PDF senza rasterizzare grafica
  e font: <https://docs.pyhanko.eu/en/latest/lib-guide/signing.html#signature-appearance-generation>
- Il profilo PAdES resta definito da ETSI EN 319 142-1; l'aspetto visibile non
  sostituisce i requisiti crittografici:
  <https://www.etsi.org/deliver/etsi_en/319100_319199/31914201/01.02.01_60/en_31914201v010201p.pdf>

## 3. Scelta grafica

Adottare come predefinita la variante **Completa bilanciata**.

Dimensione iniziale:

- larghezza: `240 pt`;
- altezza: `92 pt`;
- margine pagina: `24 pt`;
- rapporto circa `2,61 : 1`;
- variante compatta: `190 × 68 pt`, soltanto quando lo spazio disponibile non
  permette la variante completa o l'utente la sceglie esplicitamente.

Il riquadro usa:

- sfondo bianco opaco per rimanere leggibile su qualunque documento;
- bordo blu sottile, circa `1–1,5 pt`;
- angoli leggermente arrotondati, se ottenibili senza rasterizzazione;
- colonna sinistra azzurro molto chiaro, larga circa il 22–25%;
- simbolo lineare neutro della firma, senza spunta di validazione;
- testo principale antracite;
- blu soltanto per titolo, bordo e piccoli elementi di gerarchia;
- font Noto Sans o altro sans-serif incorporato nel PDF;
- nessuna ombra, gradiente, trasparenza complessa o decorazione fotografica.

Il risultato deve restare leggibile in stampa in scala di grigi.

## 4. Gerarchia del contenuto

### 4.1 Colonna sinistra

```text
[simbolo lineare]

FIRMA
DIGITALE
PAdES B-B
```

`PAdES B-B` descrive il profilo prodotto, non lo stato di validazione.

### 4.2 Corpo principale

Ordine:

```text
FIRMATO DIGITALMENTE DA
NOME COGNOME
Organizzazione · Ruolo

DATA E ORA                     MOTIVO
05/09/2026 · 10:48:32 CEST     Approvazione del documento

LUOGO                          CERTIFICATO EMESSO DA
Roma, Italia                   ArubaPEC EU Qualified CA G1

Firma n. 2 nel documento · SHA-256
Verificare la firma con un lettore PDF
```

Il nome è l'elemento visivo dominante. Organizzazione e ruolo sono secondari.
Le etichette sono piccole ma non inferiori a una dimensione equivalente a
`6,5 pt` nel PDF finale; i valori non devono scendere sotto `7,5 pt`. Il nome è
tra `11 e 13 pt`, compatibilmente con la lunghezza.

## 5. Informazioni e provenienza

| Informazione | Obbligatoria | Provenienza | Regola |
|---|---:|---|---|
| nome firmatario | sì | CN o nome leggibile del certificato | mai usare l'etichetta tecnica se è disponibile il nome X.509 |
| organizzazione | no | attributo O del subject | omettere la riga se assente |
| ruolo/unità | no | OU, titolo configurato o valore esplicito | non inventare un ruolo |
| data e ora | sì | istante usato nei metadati firma | includere secondi e fuso/offset |
| motivo | no | `SignatureConfig.reason` | omettere il blocco se vuoto |
| luogo | no | `SignatureConfig.location` | omettere il blocco se vuoto |
| emittente | sì nella variante completa | CN leggibile dell'issuer | abbreviare visivamente, conservare il valore completo nei metadati |
| profilo | sì | configurazione effettiva | inizialmente `PAdES B-B` |
| digest | sì | algoritmo effettivo | inizialmente `SHA-256` |
| numero firma | sì | conteggio firme incorporate + 1 | `Firma n. N nel documento` |
| nota verifica | sì nella variante completa | testo fisso | non contiene un giudizio di validità |

Non mostrare nel riquadro:

- seriale completo del certificato;
- identificatore PKCS#11;
- percorso del file;
- identificatore del batch;
- codice fiscale estratto senza una decisione esplicita;
- intero distinguished name, salvo modalità diagnostica non destinata al PDF.

Questi dati aumentano il rumore e possono esporre informazioni personali o
tecniche senza migliorare il riconoscimento della firma.

## 6. Gestione dei valori mancanti e lunghi

- I campi opzionali vuoti non producono etichette vuote.
- I blocchi rimanenti ridistribuiscono lo spazio verticalmente.
- Il nome può andare su due righe prima di ridurre il font.
- Organizzazione, motivo, luogo ed emittente possono essere troncati soltanto
  nell'aspetto visibile. I valori completi restano nei metadati firmati quando
  applicabile.
- Non usare puntini di sospensione se il testo diventa ambiguo; preferire una
  variante più alta o la modalità compatta con meno campi.
- Supportare accenti e caratteri Unicode presenti nei certificati reali.
- Se il subject X.509 non può essere analizzato, usare una versione ripulita
  della stringa subject; come ultima scelta usare l'etichetta del certificato.

## 7. Data e marca temporale

La versione corrente produce PAdES B-B senza TSA. Il testo deve quindi dire
semplicemente `Data e ora`, mai `Marca temporale` o `Data certa`.

Formati:

```text
05/09/2026 · 10:48:32 CEST
05/09/2026 · 10:48:32 +02:00
```

Preferire l'abbreviazione del fuso solo quando non è ambigua; conservare sempre
un offset corretto nei metadati. Se in futuro viene implementato PAdES B-T con
TSA verificata, l'aspetto potrà distinguere `Data di firma` e `Marca temporale`
soltanto dopo una nuova decisione di prodotto.

## 8. Tecnologia di rendering

L'aspetto deve essere vettoriale. Non generare uno screenshot o una bitmap del
riquadro.

Percorso consigliato:

1. creare per ogni firma una piccola pagina PDF delle dimensioni esatte del
   riquadro usando ReportLab o un renderer PDF vettoriale equivalente;
2. incorporare un font TrueType/OpenType distribuito con l'app, preferibilmente
   Noto Sans Regular e SemiBold;
3. disegnare fondi, linee, simbolo e testi come operatori vettoriali;
4. importare la pagina con `StaticStampStyle.from_pdf_file()` di pyHanko;
5. usare lo stile nel `PdfSigner` già esistente;
6. eliminare il file temporaneo dell'aspetto dopo la firma;
7. mantenere invariata la scrittura incrementale e la verifica post-firma.

La documentazione pyHanko dichiara che l'importazione da PDF conserva le
operazioni vettoriali e i font senza rasterizzazione. Prima di consolidare
ReportLab, Codex deve verificare con un piccolo spike che:

- il font risulti incorporato;
- il riquadro sia nitido almeno al 400% di zoom;
- il testo sia selezionabile quando il lettore lo consente;
- il PDF firmato continui a superare la verifica esistente;
- una seconda firma preservi la prima;
- il packaging includa font e risorse.

Se `StaticStampStyle` non consente il risultato richiesto con l'API pubblica
della versione bloccata, implementare un renderer basato sulle API pubbliche di
contenuto PDF di pyHanko. Non fare affidamento su API private senza test e nota
architetturale.

## 9. Modello dati proposto

Separare i dati dall'aspetto:

```python
@dataclass(frozen=True, slots=True)
class SignatureAppearanceData:
    signer_name: str
    signing_time: datetime
    issuer_name: str
    profile: str
    digest_algorithm: str
    signature_number: int
    organization: str = ""
    role: str = ""
    reason: str = ""
    location: str = ""


class SignatureAppearanceVariant(StrEnum):
    COMPLETE = "complete"
    COMPACT = "compact"
```

Creare un servizio indipendente dalla GUI:

```python
class SignatureAppearanceRenderer(Protocol):
    def render_pdf(
        self,
        data: SignatureAppearanceData,
        *,
        width_points: float,
        height_points: float,
        variant: SignatureAppearanceVariant,
    ) -> Path: ...
```

Il percorso restituito è temporaneo e deve essere gestito con un context manager
oppure da un oggetto che implementi cleanup deterministico.

## 10. Configurazione

Aggiungere alla configurazione soltanto:

```text
appearance_variant = "complete"
width_points = 240.0
height_points = 92.0
```

Mantenere `reason` e `location` esistenti. Colore, font, etichette e struttura
restano inizialmente parte del design di prodotto, non opzioni utente. Evitare
decine di impostazioni che renderebbero impossibile garantire leggibilità.

La migrazione da configurazioni versione 1 deve applicare i nuovi valori senza
perdere le impostazioni esistenti. Valutare l'aumento di `config_version` solo
se il repository non può gestire i nuovi campi opzionali in modo retrocompatibile.

## 11. Anteprima nell'interfaccia

La pagina `Controlla e firma` deve usare lo stesso modello dati e lo stesso
renderer della firma reale. Non ricostruire il riquadro con un secondo layout Qt
indipendente.

Percorso consigliato:

1. generare il piccolo PDF dell'aspetto con dati reali e data di esempio;
2. mostrarlo come overlay sull'anteprima della pagina;
3. rigenerarlo quando cambiano variante, motivo, luogo o certificato;
4. sostituire la data di esempio con l'istante effettivo al momento della firma.

L'anteprima deve indicare chiaramente quando la data è dimostrativa.

## 12. Test automatici

### Dati

- estrazione CN, O, OU e issuer da certificati con ordine differente;
- fallback per subject non analizzabile;
- Unicode, accenti e nomi lunghi;
- campi opzionali vuoti;
- numero firma corretto in documento nuovo e co-firmato;
- timezone e offset espliciti.

### Rendering

- dimensione MediaBox esatta;
- presenza del font incorporato;
- assenza di bitmap a pieno riquadro;
- testo atteso estraibile dal PDF dell'aspetto;
- nessun testo vietato come `firma valida`;
- nessun overflow per campioni rappresentativi;
- variante completa e compatta.

### Integrazione

- firma singola valida con il signer software di test;
- seconda firma incrementale;
- quattro preset e quattro rotazioni;
- motivo e luogo presenti sia nei metadati sia nell'aspetto quando configurati;
- output verificato dal controllo già esistente;
- file temporanei rimossi anche dopo errore.

Creare immagini golden soltanto per pochi casi stabili e con una tolleranza
documentata. Affiancare sempre controlli strutturali, perché una differenza di
rendering non deve essere l'unico criterio di correttezza.

## 13. Criteri di accettazione

- Il riquadro è interamente vettoriale e nitido al 400%.
- Nome, data/ora con fuso, emittente, profilo, digest e numero firma sono presenti
  nella variante completa.
- Organizzazione, ruolo, motivo e luogo compaiono solo quando disponibili.
- Il testo non afferma validità o presenza di TSA.
- L'aspetto resta leggibile su A4 verticale, A4 orizzontale e pagine ruotate.
- L'anteprima usa lo stesso renderer del PDF firmato.
- Una firma e una co-firma superano i test crittografici esistenti.
- Il font e tutte le risorse sono inclusi nel pacchetto Windows.
- Nessun file temporaneo dell'aspetto rimane dopo successo o errore.

## 14. Decisione implementativa

Lo spike eseguito su Windows con ReportLab 5.0.1 e pyHanko 0.37.0 ha confermato
che `StaticStampStyle.from_pdf_file()` preserva contenuto vettoriale e font
incorporato, mantiene il testo estraibile nel PDF sorgente dell'aspetto e non
altera la verifica crittografica della firma o della co-firma. È quindi stata
adottata questa soluzione usando esclusivamente API pubbliche.

Il font incorporato è Bitstream Vera Sans distribuito con ReportLab. Le due
dimensioni predefinite sono 240 × 92 pt e 190 × 68 pt. Il temporaneo è gestito
da un context manager e viene rimosso anche quando la firma genera un errore.
La resa completa è stata ispezionata a 960 × 368 pixel, equivalente al 400%.

Restano da completare l'anteprima Qt basata sul medesimo PDF generato e le prove
di stampa/scaling sui documenti reali; questi limiti non incidono sul contenuto
vettoriale già applicato ai PDF firmati.
