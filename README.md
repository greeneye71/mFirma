# mFirma

Prima versione snella di un'applicazione Windows per firmare uno o più PDF con
firma **PAdES B-B** e smart card/token **PKCS#11**.

La documentazione completa parte dall'[indice dei documenti](docs/README.md).

La modalità implementata è volutamente una sola: firma visibile PAdES con
output nella stessa cartella e suffisso `_firmato`. Il batch è seriale e apre
una sola sessione PKCS#11; il middleware può comunque richiedere nuovamente il
PIN per ogni firma. PAdES usa aggiornamenti incrementali, quindi una firma già
presente viene preservata ed è possibile aggiungerne un'altra selezionando
manualmente il PDF firmato.

## Avvio per sviluppo

Richiede Windows 11 x64, Python 3.11+ x64 e il middleware ufficiale del token.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.lock
.venv\Scripts\python -m pip install -e . --no-deps
.venv\Scripts\python -m mfirma
```

Dopo l'installazione iniziale si può anche fare doppio clic su
`avvia_mFirma.cmd`.

Nella finestra:

1. scegli la cartella monitorata;
2. indica la DLL PKCS#11, l'etichetta del token e quella del certificato;
3. aggiorna l'elenco o aggiungi PDF manualmente;
4. seleziona più righe e premi `Firma selezionati`;
5. conferma il riepilogo e inserisci il PIN. Lascia il PIN vuoto soltanto se il
   middleware usa il proprio dialogo protetto.

Il PIN non viene salvato. I file originali non vengono modificati e un output
esistente viene saltato.

Per aggiungere una seconda firma allo stesso PDF, usa `Aggiungi PDF` sul primo
output firmato e scegli preferibilmente un altro preset, così i due riquadri
visibili non si sovrappongono.

Per ispezionare token e certificati pubblici senza chiedere il PIN:

```powershell
.venv\Scripts\python -m mfirma.probe "C:\percorso\middleware.dll"
```

Alcuni dispositivi non espongono certificati senza login: in quel caso il probe
lo segnala senza tentare PIN.

## Stato dell'MVP

Implementato:

- scansione ricorsiva per persona e selezione multipla;
- aggiunta manuale di PDF, inclusi PDF già firmati per la co-firma;
- quattro preset visibili e ultima pagina;
- batch seriale con annullamento tra un file e il successivo;
- sessione PKCS#11 condivisa dal batch;
- output temporaneo, pubblicazione atomica e nessuna sovrascrittura;
- controllo post-firma: una nuova firma incorporata, integra e
  crittograficamente valida;
- configurazione JSON senza PIN;
- probe PKCS#11 senza autenticazione e test del nucleo senza token.

Rimandato fino ai test reali: tray, menu di Esplora file, anteprima grafica,
selezione guidata del certificato, destinazione separata, packaging e provider
CSP/CNG. Questi punti sono pianificati in [docs/PIANO.md](docs/PIANO.md).

## Test

```powershell
python -m pytest
```

I test automatici non provano la validità legale o la compatibilità hardware.
La scheda da compilare con dispositivo e file reali è in
[docs/device-compatibility.md](docs/device-compatibility.md).

## Documentazione

- [Manuale utente](docs/MANUALE_UTENTE.md)
- [Installazione](docs/INSTALLAZIONE.md)
- [Architettura](docs/ARCHITETTURA.md)
- [Piano di collaudo](docs/COLLAUDO.md)
- [Risoluzione dei problemi](docs/RISOLUZIONE_PROBLEMI.md)
- [Sicurezza](docs/SICUREZZA.md)
- [Limiti noti](docs/LIMITI_NOTI.md)
- [Piano di progetto](docs/PIANO.md)
