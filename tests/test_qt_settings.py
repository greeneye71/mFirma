from __future__ import annotations

import threading
from dataclasses import asdict

import pytest
from PySide6.QtCore import QThreadPool

from mfirma.config import AppConfig, ConfigRepository
from mfirma.discovery import (
    CertificateCandidate,
    DiscoveryResult,
    ModuleCandidate,
    TokenCandidate,
)
from mfirma.ui.dialogs import (
    CertificateSelectionDialog,
    ModuleSelectionDialog,
    TokenSelectionDialog,
)
from mfirma.ui.main_window import MFirmaQtWindow
from mfirma.ui.pages.settings_page import SettingsPage
from mfirma.ui.workers import (
    DiscoveryController,
    DiscoveryOperation,
    DiscoveryOutcome,
)


def _module(workdir, *, multiple: bool = False) -> ModuleCandidate:
    certificates = (
        CertificateCandidate(
            label="Autenticazione",
            id_hex="01",
            subject="CN=Utente",
            issuer="CN=CA Prova",
            not_after="2027-01-01",
            digital_signature=True,
        ),
        CertificateCandidate(
            label="Firma documenti",
            id_hex="445333",
            subject="CN=Firmatario Prova",
            issuer="CN=CA Firma",
            not_after="2028-01-01",
            content_commitment=True,
        ),
    )
    if not multiple:
        certificates = certificates[1:]
    token = TokenCandidate(
        slot_id=7,
        label="Token Firma",
        serial="SER-1",
        serial_hex="5345522d31",
        manufacturer="Produttore Prova",
        model="Carta Prova",
        certificates=certificates,
    )
    return ModuleCandidate(
        path=workdir / "vendor-pkcs11.dll",
        architecture="x64",
        source="percorso scelto",
        token_labels=("Token Firma",),
        certificate_labels=tuple(item.label for item in certificates),
        document_signing_labels=("Firma documenti",),
        certificate_ids=tuple((item.label, item.id_hex) for item in certificates),
        certificates=certificates,
        tokens=(token,),
    )


def test_settings_page_roundtrip_all_fields_and_variant_defaults(qtbot):
    config = AppConfig()
    page = SettingsPage(config)
    qtbot.addWidget(page)

    page.monitor_root.setText(r"\\server\Da firmare")
    page.recursive.setChecked(False)
    page.stability_seconds.setValue(12)
    page.token_label.setText("Token A")
    page.key_label.setText("Chiave manuale")
    page.preset.setCurrentIndex(page.preset.findData("top_left"))
    page.appearance_variant.setCurrentIndex(
        page.appearance_variant.findData("compact")
    )
    page.margin_points.setValue(18.5)
    page.reason.setText("Approvazione")
    page.location.setText("Roma")
    page.output_suffix.setText("_sig")

    updated = page.build_config()

    assert updated.monitor.root == r"\\server\Da firmare"
    assert updated.monitor.recursive_within_person is False
    assert updated.monitor.stability_seconds == 12
    assert updated.pkcs11.token_label == "Token A"
    assert updated.pkcs11.token_serial == ""
    assert updated.pkcs11.key_label == "Chiave manuale"
    assert updated.signature.preset == "top_left"
    assert updated.signature.appearance_variant == "compact"
    assert updated.signature.width_points == 190.0
    assert updated.signature.height_points == 68.0
    assert updated.signature.margin_points == 18.5
    assert updated.signature.reason == "Approvazione"
    assert updated.signature.location == "Roma"
    assert updated.output.suffix == "_sig"
    assert "pin" not in asdict(updated)["pkcs11"]


def test_settings_page_rejects_invalid_output_suffix(qtbot):
    page = SettingsPage(AppConfig())
    qtbot.addWidget(page)
    page.output_suffix.setText("firma/non valida")

    with pytest.raises(ValueError, match="Suffisso"):
        page.build_config()


def test_settings_controls_have_accessible_names(qtbot):
    page = SettingsPage(AppConfig())
    qtbot.addWidget(page)

    assert page.monitor_root.accessibleName() == "Cartella monitorata"
    assert page.module_path.accessibleName() == "DLL PKCS11"
    assert page.certificate_label.accessibleName() == "Etichetta certificato"
    assert page.reason.accessibleName() == "Motivo firma opzionale"
    assert page.save_button.accessibleName() == "Salva impostazioni"


def test_module_candidate_sets_token_certificate_and_public_id(qtbot, workdir):
    page = SettingsPage(AppConfig())
    qtbot.addWidget(page)
    candidate = _module(workdir)

    assert page.apply_module_candidate(candidate) is False
    config = page.build_config()

    assert config.pkcs11.module_path == str(candidate.path)
    assert config.pkcs11.token_label == "Token Firma"
    assert config.pkcs11.token_serial == "5345522d31"
    assert config.pkcs11.certificate_label == "Firma documenti"
    assert config.pkcs11.certificate_id == "445333"

    page.module_path.setText(str(workdir / "altra.dll"))
    assert page.build_config().pkcs11.certificate_id == ""


def test_discovery_dialogs_expose_real_candidates(qtbot, workdir):
    candidate = _module(workdir, multiple=True)
    result = DiscoveryResult((candidate,), paths_checked=1, rejected=0)
    module_dialog = ModuleSelectionDialog(result)
    certificate_dialog = CertificateSelectionDialog(candidate)
    token_dialog = TokenSelectionDialog(candidate)
    qtbot.addWidget(module_dialog)
    qtbot.addWidget(certificate_dialog)
    qtbot.addWidget(token_dialog)

    assert module_dialog.selected_candidate() == candidate
    assert certificate_dialog.model.data(
        certificate_dialog.model.index(0, 1)
    ) == "Firma documenti"
    assert certificate_dialog.selected_label() == "Firma documenti"
    assert token_dialog.selected_token() == candidate.tokens[0]


def test_selecting_one_of_multiple_tokens_keeps_its_certificate_id(
    qtbot, workdir
):
    first_certificate = CertificateCandidate(
        label="Firma", id_hex="01", content_commitment=True
    )
    second_certificate = CertificateCandidate(
        label="Firma", id_hex="02", content_commitment=True
    )
    first = TokenCandidate(
        slot_id=1,
        label="Token uguale",
        serial="SER-A",
        serial_hex="5345522d41",
        certificates=(first_certificate,),
    )
    second = TokenCandidate(
        slot_id=2,
        label="Token uguale",
        serial="SER-B",
        serial_hex="5345522d42",
        certificates=(second_certificate,),
    )
    candidate = ModuleCandidate(
        path=workdir / "vendor-pkcs11.dll",
        architecture="x64",
        source="test",
        token_labels=("Token uguale",),
        certificate_labels=("Firma",),
        document_signing_labels=("Firma",),
        certificate_ids=(("Firma", "01"),),
        certificates=(first_certificate,),
        tokens=(first, second),
    )
    page = SettingsPage(AppConfig())
    qtbot.addWidget(page)

    assert page.apply_module_candidate(candidate) is False
    assert page.selected_token(candidate) is None
    assert page.select_token(candidate, second) is False
    config = page.build_config()

    assert config.pkcs11.token_label == "Token uguale"
    assert config.pkcs11.token_serial == "5345522d42"
    assert config.pkcs11.certificate_label == "Firma"
    assert config.pkcs11.certificate_id == "02"


def test_discovery_controller_runs_probe_outside_gui_thread(qtbot, workdir):
    gui_thread = threading.current_thread()
    calls = []

    def fake_discoverer(**options):
        calls.append((threading.current_thread(), options))
        return DiscoveryResult((_module(workdir),), paths_checked=1, rejected=0)

    pool = QThreadPool()
    controller = DiscoveryController(discoverer=fake_discoverer, thread_pool=pool)
    outcomes: list[DiscoveryOutcome] = []
    controller.operationSucceeded.connect(outcomes.append)

    with qtbot.waitSignal(controller.operationSucceeded, timeout=3000):
        assert controller.inspect(workdir / "vendor-pkcs11.dll", show_certificates=True)
        assert not controller.discover()

    assert calls[0][0] is not gui_thread
    assert calls[0][1]["search_roots"] == ()
    assert outcomes[0].operation is DiscoveryOperation.INSPECT
    assert outcomes[0].show_certificates is True
    assert controller.busy is False


def test_main_window_saves_settings_without_pin(qtbot, workdir):
    repository = ConfigRepository(workdir / "config.json")
    repository.save(AppConfig())
    window = MFirmaQtWindow(repository, auto_scan=False)
    qtbot.addWidget(window)
    window.settings_page.monitor_root.setText(str(workdir / "documenti"))
    window.settings_page.output_suffix.setText("_firmato_qt")

    window.save_settings()

    saved = repository.load()
    assert saved.monitor.root == str(workdir / "documenti")
    assert saved.output.suffix == "_firmato_qt"
    assert "pin" not in repository.path.read_text(encoding="utf-8").casefold()
    assert window.settings_page.save_status.text() == "Impostazioni salvate"
