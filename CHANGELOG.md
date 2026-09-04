# Changelog

## Non rilasciato

- sostituito il riquadro testuale minimo con un aspetto firma vettoriale
  completo/compatto, font incorporato e informazioni neutrali verificabili;
- aggiunti modello `SignatureAppearanceData`, numero progressivo della firma,
  timezone esplicito e cleanup deterministico del temporaneo dell'aspetto;
- aggiornati i valori predefiniti a 240 × 92 pt, con migrazione del precedente
  default 180 × 60 pt;
- aggiunto `installa_mFirma.cmd` per creare o riparare automaticamente `.venv`;
- `avvia_mFirma.cmd` prepara l'ambiente al primo avvio se necessario;
- aggiunte istruzioni per installare Python 3.13 tramite `winget`.
- aggiunto il rilevamento assistito delle DLL PKCS#11 x64 con probe isolato.
- lettura automatica e scelta guidata dell'etichetta del certificato dopo la
  selezione della DLL.
- associazione della chiave privata tramite ID PKCS#11 del certificato, senza
  presumere che le due etichette coincidano.
- aggiunto `Leggi card…`, con elenco dei certificati pubblici e dettagli su uso,
  intestatario, emittente e scadenza.
- gli errori del dispositivo durante la firma non sono più classificati come
  PDF non valido.

## 0.1.0 - 2026-09-04

- prima GUI Tkinter;
- scansione per persona e selezione multipla;
- firma visibile PAdES B-B tramite provider PKCS#11;
- batch seriale con una sessione e annullamento controllato;
- possibilità di aggiungere firme incrementali a un PDF già firmato;
- quattro preset con gestione delle rotazioni;
- output nella stessa cartella, temporaneo e senza sovrascrittura;
- verifica crittografica immediata della nuova firma;
- configurazione atomica senza PIN;
- probe pubblico PKCS#11;
- suite automatica e documentazione iniziale.
