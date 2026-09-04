# Compatibilità dispositivo

Stato: **da compilare con il dispositivo reale**.

Non inserire PIN, dati personali non necessari o copie di chiavi/certificati
privati in questo documento.

| Voce | Valore |
|---|---|
| Data e PC di prova | Da verificare |
| Token, modello, firmware | Da verificare |
| Middleware e versione | Da verificare |
| Percorso DLL PKCS#11 | Da verificare |
| Architettura DLL/processo | Da verificare (attesa x64/x64) |
| Token label / seriale | Da verificare |
| Certificate label / ID | Da verificare |
| Algoritmo chiave e meccanismo | Da verificare |
| Comportamento PIN | Da verificare |
| Riuso sessione nel batch | Da verificare |
| Profilo validato | PAdES B-B candidato |
| Visualizzatori di controllo | Da concordare |

## Prove da registrare

- probe senza autenticazione;
- una firma visibile verificata;
- seconda firma sullo stesso PDF, preservando la prima;
- batch da 10 e 100 file;
- PIN annullato e PIN errato una sola volta;
- rimozione del token tra due file;
- PDF reali anonimizzati, inclusi ruotati e già firmati.

