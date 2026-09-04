from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from .batch import BatchOrchestrator
from .config import AppConfig, ConfigRepository
from .discovery import DiscoveryResult, ModuleCandidate, discover_pkcs11_modules
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
        self._certificate_ids_by_label: dict[str, str] = {}
        self._certificate_id_module_path = ""
        if self.config.pkcs11.certificate_label and self.config.pkcs11.certificate_id:
            self._certificate_ids_by_label[self.config.pkcs11.certificate_label] = (
                self.config.pkcs11.certificate_id
            )
            self._certificate_id_module_path = self.config.pkcs11.module_path

        self._build_variables()
        self._build_ui()
        self.root.after(100, self._poll_events)
        if self.config.pkcs11.module_path and not self.config.pkcs11.certificate_id:
            self.root.after(
                250,
                lambda: self._start_selected_module_probe(
                    Path(self.config.pkcs11.module_path)
                ),
            )

    def _build_variables(self) -> None:
        self.monitor_root = tk.StringVar(value=self.config.monitor.root)
        self.module_path = tk.StringVar(value=self.config.pkcs11.module_path)
        self.token_label = tk.StringVar(value=self.config.pkcs11.token_label)
        self.certificate_label = tk.StringVar(
            value=self.config.pkcs11.certificate_label
        )
        self.key_label = tk.StringVar(value=self.config.pkcs11.key_label)
        self.preset = tk.StringVar(value=self.config.signature.preset)
        self.appearance_variant = tk.StringVar(
            value=(
                "Compatto"
                if self.config.signature.appearance_variant == "compact"
                else "Completo"
            )
        )
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
        ttk.Button(settings, text="Sfoglia…", command=self._choose_root).grid(row=0, column=3)

        ttk.Label(settings, text="DLL PKCS#11").grid(row=1, column=0, sticky="w", pady=(5, 0))
        ttk.Entry(settings, textvariable=self.module_path).grid(
            row=1, column=1, sticky="ew", padx=6, pady=(5, 0)
        )
        ttk.Button(settings, text="Rileva…", command=self._start_module_discovery).grid(
            row=1, column=2, pady=(5, 0)
        )
        ttk.Button(settings, text="Sfoglia…", command=self._choose_module).grid(
            row=1, column=3, padx=(5, 0), pady=(5, 0)
        )

        labels = ttk.Frame(settings)
        labels.grid(row=2, column=0, columnspan=4, sticky="ew", pady=(8, 0))
        for column in (1, 3):
            labels.columnconfigure(column, weight=1)
        ttk.Label(labels, text="Token").grid(row=0, column=0)
        ttk.Entry(labels, textvariable=self.token_label, width=16).grid(
            row=0, column=1, sticky="ew", padx=(4, 10)
        )
        ttk.Label(labels, text="Certificato").grid(row=0, column=2)
        ttk.Entry(labels, textvariable=self.certificate_label, width=18).grid(
            row=0, column=3, sticky="ew", padx=(4, 10)
        )
        ttk.Button(
            labels, text="Leggi card…", command=self._read_card_certificates
        ).grid(row=0, column=4, padx=(0, 10))
        ttk.Label(labels, text="Chiave (opz.)").grid(
            row=1, column=0, sticky="w", pady=(6, 0)
        )
        ttk.Entry(labels, textvariable=self.key_label, width=16).grid(
            row=1, column=1, sticky="ew", padx=(4, 10), pady=(6, 0)
        )
        ttk.Label(labels, text="Posizione").grid(
            row=1, column=2, sticky="w", pady=(6, 0)
        )
        ttk.Combobox(
            labels,
            textvariable=self.preset,
            values=("top_left", "top_right", "bottom_left", "bottom_right"),
            state="readonly",
            width=14,
        ).grid(row=1, column=3, sticky="ew", padx=(4, 10), pady=(6, 0))
        ttk.Label(labels, text="Aspetto").grid(
            row=1, column=4, sticky="w", pady=(6, 0)
        )
        ttk.Combobox(
            labels,
            textvariable=self.appearance_variant,
            values=("Completo", "Compatto"),
            state="readonly",
            width=12,
        ).grid(row=1, column=5, sticky="ew", padx=(4, 0), pady=(6, 0))

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
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("mFirma", "Attendere la fine dell'operazione in corso.")
            return
        selected = filedialog.askopenfilename(
            title="DLL PKCS#11", filetypes=(("Librerie Windows", "*.dll"), ("Tutti", "*.*"))
        )
        if selected:
            self.module_path.set(selected)
            self._start_selected_module_probe(Path(selected))

    def _read_card_certificates(self) -> None:
        module = self.module_path.get().strip()
        if not module:
            messagebox.showinfo(
                "Leggi card",
                "Prima seleziona la DLL PKCS#11 con Rileva… oppure Sfoglia….",
            )
            return
        self._start_selected_module_probe(
            Path(module), show_certificate_list=True
        )

    def _start_selected_module_probe(
        self, path: Path, *, show_certificate_list: bool = False
    ) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("mFirma", "Attendere la fine dell'operazione in corso.")
            return
        self.status.set(f"Lettura dei certificati da {path.name}…")

        def work() -> None:
            try:
                result = discover_pkcs11_modules(
                    search_roots=(), extra_paths=(path,), probe_timeout=8.0
                )
                self.events.put(
                    ("module_inspected", (path, result, show_certificate_list))
                )
            except Exception as exc:
                self.events.put(("error", f"Lettura della DLL non riuscita:\n{exc}"))

        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()

    def _start_module_discovery(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("mFirma", "Attendere la fine dell'operazione in corso.")
            return
        configured = self.module_path.get().strip()
        extra_paths = (Path(configured),) if configured else ()
        self.status.set("Ricerca delle DLL PKCS#11 in corso…")

        def work() -> None:
            try:
                result = discover_pkcs11_modules(extra_paths=extra_paths)
                self.events.put(("modules_found", result))
            except Exception as exc:
                self.events.put(("error", f"Rilevamento DLL non riuscito:\n{exc}"))

        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()

    def _show_module_candidates(self, result: DiscoveryResult) -> None:
        if not result.candidates:
            self.status.set("Nessuna DLL PKCS#11 rilevata")
            messagebox.showinfo(
                "Rileva DLL PKCS#11",
                "Nessuna DLL PKCS#11 x64 valida è stata rilevata.\n\n"
                f"Percorsi candidati controllati: {result.paths_checked}.\n"
                "Collega il dispositivo, verifica che il middleware ufficiale "
                "sia installato oppure usa Sfoglia…",
            )
            return

        window = tk.Toplevel(self.root)
        window.title("DLL PKCS#11 rilevate")
        window.geometry("980x360")
        window.minsize(720, 280)
        window.transient(self.root)

        ttk.Label(
            window,
            text="Seleziona il middleware da usare. La scelta non richiede il PIN.",
            padding=(12, 12, 12, 8),
        ).pack(fill="x")
        frame = ttk.Frame(window, padding=(12, 0))
        frame.pack(fill="both", expand=True)
        columns = ("path", "tokens", "certificates", "source")
        table = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse")
        table.heading("path", text="DLL x64")
        table.heading("tokens", text="Token rilevati")
        table.heading("certificates", text="Certificati pubblici")
        table.heading("source", text="Origine ricerca")
        table.column("path", width=400, anchor="w")
        table.column("tokens", width=120, anchor="w")
        table.column("certificates", width=220, anchor="w")
        table.column("source", width=180, anchor="w")
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=table.yview)
        table.configure(yscrollcommand=scrollbar.set)
        table.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        by_row: dict[str, ModuleCandidate] = {}
        for index, candidate in enumerate(result.candidates):
            row = f"module-{index}"
            token_text = ", ".join(candidate.token_labels) or "nessuno collegato"
            certificate_text = (
                ", ".join(
                    f"{label} (firma documenti)"
                    if label in candidate.document_signing_labels
                    else label
                    for label in candidate.certificate_labels
                )
                or "—"
            )
            table.insert(
                "",
                "end",
                iid=row,
                values=(
                    str(candidate.path),
                    token_text,
                    certificate_text,
                    candidate.source,
                ),
            )
            by_row[row] = candidate
        first_row = next(iter(by_row))
        table.selection_set(first_row)
        table.focus(first_row)

        def use_selected() -> None:
            selection = table.selection()
            if not selection:
                return
            candidate = by_row[selection[0]]
            window.destroy()
            self._apply_module_candidate(candidate)

        buttons = ttk.Frame(window, padding=12)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Annulla", command=window.destroy).pack(side="right")
        ttk.Button(buttons, text="Usa selezionata", command=use_selected).pack(
            side="right", padx=(0, 8)
        )
        table.bind("<Double-1>", lambda _event: use_selected())
        window.protocol("WM_DELETE_WINDOW", window.destroy)
        window.grab_set()
        self.status.set(f"{len(result.candidates)} DLL PKCS#11 rilevate")

    def _finish_module_inspection(
        self,
        path: Path,
        result: DiscoveryResult,
        show_certificate_list: bool = False,
    ) -> None:
        if not result.candidates:
            self.status.set(f"DLL non riconosciuta: {path.name}")
            messagebox.showwarning(
                "Leggi certificati",
                "Non è stato possibile leggere questa DLL come modulo PKCS#11 x64.\n\n"
                "Controlla che sia la libreria indicata dal produttore e che abbia "
                "la stessa architettura dell'applicazione.",
            )
            return
        self._apply_module_candidate(
            result.candidates[0],
            force_certificate_dialog=show_certificate_list,
        )

    def _apply_module_candidate(
        self,
        candidate: ModuleCandidate,
        *,
        force_certificate_dialog: bool = False,
    ) -> None:
        self.module_path.set(str(candidate.path))
        self._certificate_ids_by_label = dict(candidate.certificate_ids)
        self._certificate_id_module_path = str(candidate.path)
        current_token = self.token_label.get().strip()
        if len(candidate.token_labels) == 1 and (
            not current_token or current_token not in candidate.token_labels
        ):
            self.token_label.set(candidate.token_labels[0])

        current_certificate = self.certificate_label.get().strip()
        if current_certificate not in candidate.certificate_labels:
            if len(candidate.document_signing_labels) == 1:
                self.certificate_label.set(candidate.document_signing_labels[0])
            elif len(candidate.certificate_labels) == 1:
                self.certificate_label.set(candidate.certificate_labels[0])
            elif len(candidate.certificate_labels) > 1 and not force_certificate_dialog:
                self._show_certificate_candidates(candidate)

        if force_certificate_dialog:
            if candidate.certificate_labels:
                self._show_certificate_candidates(candidate)
            else:
                messagebox.showinfo(
                    "Certificati sulla card",
                    "La card è stata letta, ma non espone certificati pubblici "
                    "senza autenticazione. Alcuni middleware richiedono il proprio "
                    "accesso protetto.",
                )

        if candidate.certificate_labels:
            self.status.set(
                f"{len(candidate.certificate_labels)} certificati letti da "
                f"{candidate.path.name}"
            )
        else:
            self.status.set(
                f"DLL selezionata: {candidate.path.name}; nessun certificato pubblico"
            )

    def _show_certificate_candidates(self, candidate: ModuleCandidate) -> None:
        window = tk.Toplevel(self.root)
        window.title("Certificati sulla card")
        window.geometry("1100x380")
        window.minsize(760, 280)
        window.transient(self.root)

        ttk.Label(
            window,
            text=(
                "Certificati pubblici letti dalla card senza richiedere il PIN. "
                "Seleziona quello destinato alla firma dei documenti."
            ),
            wraplength=1040,
            padding=(12, 12, 12, 8),
        ).pack(fill="x")
        frame = ttk.Frame(window, padding=(12, 0))
        frame.pack(fill="both", expand=True)
        table = ttk.Treeview(
            frame,
            columns=("label", "purpose", "subject", "issuer", "expiry"),
            show="headings",
            selectmode="browse",
        )
        table.heading("label", text="Etichetta certificato")
        table.heading("purpose", text="Uso rilevato")
        table.heading("subject", text="Intestatario")
        table.heading("issuer", text="Emittente")
        table.heading("expiry", text="Scadenza")
        table.column("label", width=190, anchor="w")
        table.column("purpose", width=150, anchor="w")
        table.column("subject", width=310, anchor="w")
        table.column("issuer", width=310, anchor="w")
        table.column("expiry", width=100, anchor="w")
        vertical = ttk.Scrollbar(frame, orient="vertical", command=table.yview)
        horizontal = ttk.Scrollbar(frame, orient="horizontal", command=table.xview)
        table.configure(
            yscrollcommand=vertical.set,
            xscrollcommand=horizontal.set,
        )
        table.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        details_by_label = {
            certificate.label: certificate
            for certificate in candidate.certificates
        }
        ordered_labels = sorted(
            candidate.certificate_labels,
            key=lambda label: (
                label not in candidate.document_signing_labels,
                label.casefold(),
            ),
        )
        rows_by_label: dict[str, str] = {}
        for index, label in enumerate(ordered_labels):
            details = details_by_label.get(label)
            if label in candidate.document_signing_labels:
                purpose = "Firma documenti"
            elif details and details.digital_signature:
                purpose = "Firma / autenticazione"
            else:
                purpose = "Altro / non determinato"
            row = f"certificate-{index}"
            table.insert(
                "",
                "end",
                iid=row,
                values=(
                    label,
                    purpose,
                    details.subject if details else "",
                    details.issuer if details else "",
                    details.not_after if details else "",
                ),
            )
            rows_by_label[label] = row
        selected_row = rows_by_label.get(
            self.certificate_label.get().strip(), table.get_children()[0]
        )
        table.selection_set(selected_row)
        table.focus(selected_row)
        table.see(selected_row)

        def use_selected() -> None:
            selection = table.selection()
            if not selection:
                return
            label = str(table.item(selection[0], "values")[0])
            self.certificate_label.set(label)
            self.status.set(f"Certificato selezionato: {label}")
            window.destroy()

        buttons = ttk.Frame(window, padding=12)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Annulla", command=window.destroy).pack(side="right")
        ttk.Button(buttons, text="Usa certificato", command=use_selected).pack(
            side="right", padx=(0, 8)
        )
        table.bind("<Double-1>", lambda _event: use_selected())
        window.protocol("WM_DELETE_WINDOW", window.destroy)
        window.grab_set()

    def _sync_config(self) -> None:
        self.config.monitor.root = self.monitor_root.get().strip()
        self.config.pkcs11.module_path = self.module_path.get().strip()
        self.config.pkcs11.token_label = self.token_label.get().strip()
        self.config.pkcs11.certificate_label = self.certificate_label.get().strip()
        if self.config.pkcs11.module_path == self._certificate_id_module_path:
            self.config.pkcs11.certificate_id = self._certificate_ids_by_label.get(
                self.config.pkcs11.certificate_label, ""
            )
        else:
            self.config.pkcs11.certificate_id = ""
        self.config.pkcs11.key_label = self.key_label.get().strip()
        self.config.signature.preset = self.preset.get()
        variant = (
            "compact" if self.appearance_variant.get() == "Compatto" else "complete"
        )
        self.config.signature.appearance_variant = variant
        if variant == "compact":
            self.config.signature.width_points = 190.0
            self.config.signature.height_points = 68.0
        else:
            self.config.signature.width_points = 240.0
            self.config.signature.height_points = 92.0
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
                elif kind == "modules_found":
                    self._show_module_candidates(payload)  # type: ignore[arg-type]
                elif kind == "module_inspected":
                    path, result, show_certificate_list = payload  # type: ignore[misc]
                    self._finish_module_inspection(
                        path, result, show_certificate_list
                    )
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
