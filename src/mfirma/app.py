from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from .batch import BatchOrchestrator
from .config import AppConfig, ConfigRepository
from .models import DocumentCandidate, JobStatus, SignJob
from .provider import Pkcs11SigningProvider
from .scanner import candidates_from_paths, scan_root


class MFirmaApp:
    def __init__(self, root: tk.Tk, repository: ConfigRepository | None = None):
        self.root = root
        self.repository = repository or ConfigRepository()
        try:
            self.config = self.repository.load()
        except Exception as exc:
            messagebox.showwarning(
                "Configurazione",
                f"Configurazione non leggibile; uso i valori iniziali.\n\n{exc}",
            )
            self.config = AppConfig()

        self.documents: dict[str, DocumentCandidate] = {}
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self._row_documents: dict[str, DocumentCandidate] = {}
        self.cancel_event = threading.Event()
        self.worker: threading.Thread | None = None
        self.progress_window: tk.Toplevel | None = None
        self.progress_bar: ttk.Progressbar | None = None
        self.progress_label: ttk.Label | None = None

        self._build_variables()
        self._build_ui()
        self.root.after(100, self._poll_events)

    def _build_variables(self) -> None:
        self.monitor_root = tk.StringVar(value=self.config.monitor.root)
        self.module_path = tk.StringVar(value=self.config.pkcs11.module_path)
        self.token_label = tk.StringVar(value=self.config.pkcs11.token_label)
        self.certificate_label = tk.StringVar(
            value=self.config.pkcs11.certificate_label
        )
        self.key_label = tk.StringVar(value=self.config.pkcs11.key_label)
        self.preset = tk.StringVar(value=self.config.signature.preset)
        self.status = tk.StringVar(value="Pronto")

    def _build_ui(self) -> None:
        self.root.title("mFirma - Firma PDF")
        self.root.geometry("980x650")
        self.root.minsize(780, 520)

        settings = ttk.LabelFrame(self.root, text="Configurazione essenziale", padding=10)
        settings.pack(fill="x", padx=10, pady=(10, 5))
        settings.columnconfigure(1, weight=1)

        ttk.Label(settings, text="Cartella da firmare").grid(row=0, column=0, sticky="w")
        ttk.Entry(settings, textvariable=self.monitor_root).grid(
            row=0, column=1, sticky="ew", padx=6
        )
        ttk.Button(settings, text="Sfoglia…", command=self._choose_root).grid(row=0, column=2)

        ttk.Label(settings, text="DLL PKCS#11").grid(row=1, column=0, sticky="w", pady=(5, 0))
        ttk.Entry(settings, textvariable=self.module_path).grid(
            row=1, column=1, sticky="ew", padx=6, pady=(5, 0)
        )
        ttk.Button(settings, text="Sfoglia…", command=self._choose_module).grid(
            row=1, column=2, pady=(5, 0)
        )

        labels = ttk.Frame(settings)
        labels.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        for column in (1, 3, 5, 7):
            labels.columnconfigure(column, weight=1)
        ttk.Label(labels, text="Token").grid(row=0, column=0)
        ttk.Entry(labels, textvariable=self.token_label, width=16).grid(
            row=0, column=1, sticky="ew", padx=(4, 10)
        )
        ttk.Label(labels, text="Certificato").grid(row=0, column=2)
        ttk.Entry(labels, textvariable=self.certificate_label, width=18).grid(
            row=0, column=3, sticky="ew", padx=(4, 10)
        )
        ttk.Label(labels, text="Chiave (opz.)").grid(row=0, column=4)
        ttk.Entry(labels, textvariable=self.key_label, width=16).grid(
            row=0, column=5, sticky="ew", padx=(4, 10)
        )
        ttk.Label(labels, text="Posizione").grid(row=0, column=6)
        ttk.Combobox(
            labels,
            textvariable=self.preset,
            values=("top_left", "top_right", "bottom_left", "bottom_right"),
            state="readonly",
            width=14,
        ).grid(row=0, column=7, sticky="ew", padx=(4, 0))

        toolbar = ttk.Frame(self.root, padding=(10, 5))
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="Aggiorna cartella", command=self._start_scan).pack(side="left")
        ttk.Button(toolbar, text="Aggiungi PDF…", command=self._add_files).pack(
            side="left", padx=5
        )
        ttk.Button(toolbar, text="Seleziona tutti", command=self._select_all).pack(side="left")
        ttk.Button(toolbar, text="Firma selezionati", command=self._start_signing).pack(
            side="right"
        )

        table_frame = ttk.Frame(self.root, padding=(10, 0))
        table_frame.pack(fill="both", expand=True)
        columns = ("person", "name", "folder", "size")
        self.table = ttk.Treeview(
            table_frame, columns=columns, show="headings", selectmode="extended"
        )
        headings = {
            "person": "Persona",
            "name": "Documento",
            "folder": "Cartella",
            "size": "Dimensione",
        }
        widths = {"person": 150, "name": 250, "folder": 390, "size": 90}
        for column in columns:
            self.table.heading(column, text=headings[column])
            self.table.column(column, width=widths[column], anchor="w")
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=scrollbar.set)
        self.table.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        statusbar = ttk.Label(self.root, textvariable=self.status, anchor="w", padding=8)
        statusbar.pack(fill="x")

    def _choose_root(self) -> None:
        selected = filedialog.askdirectory(title="Cartella contenente le persone")
        if selected:
            self.monitor_root.set(selected)

    def _choose_module(self) -> None:
        selected = filedialog.askopenfilename(
            title="DLL PKCS#11", filetypes=(("Librerie Windows", "*.dll"), ("Tutti", "*.*"))
        )
        if selected:
            self.module_path.set(selected)

    def _sync_config(self) -> None:
        self.config.monitor.root = self.monitor_root.get().strip()
        self.config.pkcs11.module_path = self.module_path.get().strip()
        self.config.pkcs11.token_label = self.token_label.get().strip()
        self.config.pkcs11.certificate_label = self.certificate_label.get().strip()
        self.config.pkcs11.key_label = self.key_label.get().strip()
        self.config.signature.preset = self.preset.get()
        self.repository.save(self.config)

    def _start_scan(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        path = Path(self.monitor_root.get().strip())
        self.status.set("Scansione in corso…")

        def work() -> None:
            try:
                result = scan_root(
                    path,
                    recursive=self.config.monitor.recursive_within_person,
                    stability_seconds=self.config.monitor.stability_seconds,
                    output_suffix=self.config.output.suffix,
                )
                self.events.put(("scan_ok", result))
            except Exception as exc:
                self.events.put(("error", f"Scansione non riuscita:\n{exc}"))

        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()

    def _add_files(self) -> None:
        names = filedialog.askopenfilenames(
            title="Aggiungi uno o più PDF",
            filetypes=(("Documenti PDF", "*.pdf"),),
        )
        if not names:
            return
        try:
            for document in candidates_from_paths([Path(name) for name in names]):
                self.documents[str(document.source).casefold()] = document
            self._refresh_table()
        except Exception as exc:
            messagebox.showerror("Aggiungi PDF", str(exc))

    def _refresh_table(self) -> None:
        self.table.delete(*self.table.get_children())
        ordered = sorted(
            self.documents.values(),
            key=lambda item: ((item.person or "").casefold(), str(item.source).casefold()),
        )
        for index, document in enumerate(ordered):
            iid = f"doc-{index}"
            self.table.insert(
                "",
                "end",
                iid=iid,
                values=(
                    document.person or "—",
                    document.source.name,
                    str(document.source.parent),
                    self._format_size(document.size),
                ),
            )
            self.table.set(iid, "folder", str(document.source.parent))
        self._row_documents = {f"doc-{i}": doc for i, doc in enumerate(ordered)}
        self.status.set(f"{len(ordered)} PDF disponibili")

    @staticmethod
    def _format_size(size: int) -> str:
        if size < 1024:
            return f"{size} B"
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size / 1024 / 1024:.1f} MB"

    def _select_all(self) -> None:
        self.table.selection_set(self.table.get_children())

    def _start_signing(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("mFirma", "Attendere la fine dell'operazione in corso.")
            return
        selected = [self._row_documents[iid] for iid in self.table.selection()]
        if not selected:
            messagebox.showinfo("mFirma", "Seleziona almeno un PDF.")
            return
        try:
            self._sync_config()
            provider = Pkcs11SigningProvider(self.config.pkcs11, self.config.signature)
            provider.validate()
        except Exception as exc:
            messagebox.showerror("Configurazione", str(exc))
            return

        summary = (
            f"Documenti: {len(selected)}\n"
            f"Formato: PAdES B-B, SHA-256\n"
            f"Posizione: {self.config.signature.preset}, ultima pagina\n"
            f"Output: stessa cartella, suffisso {self.config.output.suffix}\n\n"
            "I sorgenti non saranno modificati. Continuare?"
        )
        if not messagebox.askokcancel("Conferma firma", summary):
            return
        pin = simpledialog.askstring(
            "PIN dispositivo",
            "Inserisci il PIN. Lascia vuoto solo se il middleware mostra il proprio dialogo.",
            show="•",
            parent=self.root,
        )
        if pin is None:
            return

        self.cancel_event.clear()
        self._show_progress(len(selected))
        orchestrator = BatchOrchestrator(provider, self.config.output.suffix)

        def report(index: int, total: int, job: SignJob) -> None:
            self.events.put(("progress", (index, total, job)))

        def work(secret: str | None) -> None:
            results = orchestrator.run(
                selected,
                pin=secret or None,
                cancel=self.cancel_event,
                progress=report,
            )
            secret = None
            self.events.put(("batch_done", results))

        self.worker = threading.Thread(target=work, args=(pin,), daemon=True)
        self.worker.start()
        pin = None

    def _show_progress(self, total: int) -> None:
        window = tk.Toplevel(self.root)
        window.title("Firma in corso")
        window.geometry("520x150")
        window.transient(self.root)
        window.protocol("WM_DELETE_WINDOW", self.cancel_event.set)
        self.progress_label = ttk.Label(window, text=f"Preparazione di {total} documenti…")
        self.progress_label.pack(fill="x", padx=16, pady=(20, 10))
        self.progress_bar = ttk.Progressbar(window, maximum=total, mode="determinate")
        self.progress_bar.pack(fill="x", padx=16)
        ttk.Button(window, text="Annulla dopo il file corrente", command=self.cancel_event.set).pack(
            pady=14
        )
        self.progress_window = window

    def _poll_events(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "scan_ok":
                    result = payload
                    self.documents = {
                        str(document.source).casefold(): document
                        for document in result.documents  # type: ignore[attr-defined]
                    }
                    self._refresh_table()
                    if result.errors:  # type: ignore[attr-defined]
                        self.status.set(
                            f"{result.total} PDF; {len(result.errors)} file non leggibili"  # type: ignore[attr-defined]
                        )
                elif kind == "progress":
                    index, total, job = payload  # type: ignore[misc]
                    if self.progress_bar:
                        self.progress_bar["value"] = index
                    if self.progress_label:
                        self.progress_label.configure(
                            text=f"{index}/{total} - {job.document.source.name}: {job.status.value}"
                        )
                elif kind == "batch_done":
                    self._finish_batch(payload)  # type: ignore[arg-type]
                elif kind == "error":
                    self.status.set("Errore")
                    messagebox.showerror("mFirma", str(payload))
        except queue.Empty:
            pass
        self.root.after(100, self._poll_events)

    def _finish_batch(self, jobs: list[SignJob]) -> None:
        if self.progress_window:
            self.progress_window.destroy()
            self.progress_window = None
        counts = {status: 0 for status in JobStatus}
        for job in jobs:
            counts[job.status] += 1
        lines = [
            f"Riusciti: {counts[JobStatus.SUCCEEDED]}",
            f"Saltati: {counts[JobStatus.SKIPPED]}",
            f"Errori: {counts[JobStatus.FAILED]}",
            f"Annullati: {counts[JobStatus.CANCELLED]}",
        ]
        failures = [job for job in jobs if job.status is JobStatus.FAILED]
        if failures:
            lines.append("\nDettagli:")
            lines.extend(
                f"- {job.document.source.name}: {job.error_code} - {job.message}"
                for job in failures[:10]
            )
        self.status.set("Batch completato")
        messagebox.showinfo("Esito firma", "\n".join(lines))


def main() -> None:
    root = tk.Tk()
    app = MFirmaApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
