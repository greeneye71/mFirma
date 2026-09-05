# Limiti noti della versione 0.1.0

## Funzioni non ancora implementate

La dashboard Qt è disponibile in modalità di migrazione, ma il flusso operativo
completo continua a usare Tkinter.

- icona nella system tray;
- avvio automatico con Windows;
- istanza singola e inoltro da una seconda invocazione;
- menu contestuale di Esplora file;
- destinazione separata con conservazione dell'albero relativo;
- cronologia, log rotanti ed esportazione del riepilogo;
- pacchetto autonomo e installer Windows con disinstallazione per PC senza
  Python; è disponibile soltanto lo script locale `installa_mFirma.cmd`;
- provider Windows CSP/CNG;
- TSA e profili PAdES B-T, B-LT e B-LTA;
- nella dashboard Qt: PIN, firma, avanzamento, esito e tray;

## Limiti operativi

- viene firmata sempre l'ultima pagina;
- il nome di output aggiunge sempre `_firmato`;
- una co-firma aggiunge nuovamente il suffisso;
- le firme multiple nello stesso preset possono sovrapporsi visivamente;
- la scansione è manuale, non periodica;
- i file modificati negli ultimi cinque secondi non compaiono nella scansione;
- il certificato è presentato tramite etichetta, mentre la chiave viene
  associata automaticamente tramite ID PKCS#11 quando disponibile;
- un PDF cifrato non è supportato;
- la compatibilità dipende dalla DLL e dal middleware del produttore;
- il rilevamento usa posizioni e nomi plausibili e non può garantire di trovare
  tutti i middleware PKCS#11 esistenti;
- la richiesta PIN protetta del middleware deve essere provata sul dispositivo;
- la validazione automatica non determina validità qualificata o legale.

## Stato del supporto

Nessun modello di token è ancora dichiarato ufficialmente supportato. La
struttura software e la firma PAdES sono state verificate con una chiave software
di test; PKCS#11 resta da verificare con hardware reale.
