# Documentazione mFirma

Questa cartella raccoglie la documentazione della versione 0.1.0. Il documento
di specifica originale rimane in `SPECIFICA_FIRMA_PDF_WINDOWS.md` nella radice
del progetto.

## Per chi usa l'applicazione

- [Manuale utente](MANUALE_UTENTE.md): avvio, selezione e firma dei PDF.
- [Registro delle firme](REGISTRO_FIRME.md): dati per documento, identità della
  postazione e predisposizione per un futuro database condiviso.
- [Installazione e configurazione](INSTALLAZIONE.md): primo avvio automatico,
  riparazione dell'ambiente Python, token e DLL PKCS#11.
- [Risoluzione dei problemi](RISOLUZIONE_PROBLEMI.md): errori frequenti e
  controlli da eseguire.
- [Limiti noti](LIMITI_NOTI.md): cosa non è ancora incluso nella versione.

## Per sviluppo e collaudo

- [Architettura](ARCHITETTURA.md): componenti, flusso dei dati e scelte
  tecniche.
- [Specifica dell'interfaccia](SPECIFICA_INTERFACCIA.md): direzione approvata,
  schermate, componenti PySide6/Fluent, stati e sequenza di implementazione.
- [Aspetto visibile della firma](SPECIFICA_ASPETTO_FIRMA.md): contenuti,
  gerarchia grafica, rendering vettoriale e test del riquadro applicato al PDF.
- [Prompt per il prossimo sviluppo](PROMPT_PROSSIMO_SVILUPPO.md): istruzioni
  operative pronte da affidare a Codex per l'implementazione.
- [Piano di progetto](PIANO.md): fasi successive e rischi aperti.
- [Piano di collaudo](COLLAUDO.md): prove automatiche e prove con hardware.
- [Sicurezza](SICUREZZA.md): PIN, file, dipendenze e responsabilità operative.
- [Compatibilità dispositivo](device-compatibility.md): scheda da compilare
  durante le prove reali.

## Stato della documentazione

La documentazione utente descrive esclusivamente il comportamento implementato
nella versione 0.1.0. I documenti di progetto possono descrivere evoluzioni
approvate ma non ancora implementate e le indicano esplicitamente.
