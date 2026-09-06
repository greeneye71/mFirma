from contextlib import contextmanager
from dataclasses import replace
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QDialog, QMessageBox

from mfirma.config import AppConfig, ConfigRepository
from mfirma.discovery import CertificateCandidate, DiscoveryResult, ModuleCandidate, TokenCandidate
from mfirma.models import DocumentCandidate, JobStatus, SignaturePositionPlan
from mfirma.ui.dialogs import CertificateSelectionDialog, PinDialog, TokenSelectionDialog
from mfirma.ui.main_window import MFirmaQtWindow
from mfirma.ui.workers import DiscoveryController


@pytest.fixture
def signing_flow(qtbot, workdir, monkeypatch):
    module = workdir / "vendor.dll"
    module.write_bytes(b"test middleware")
    certificate = CertificateCandidate(
        label="Firma", id_hex="01", subject="CN=Persona A", content_commitment=True,
    )
    token = TokenCandidate(
        slot_id=1, label="Tessera", serial="A", serial_hex="41",
        certificates=(certificate,),
    )
    candidate = ModuleCandidate(path=module, architecture="x64", source="test", tokens=(token,))
    state = SimpleNamespace(
        candidate=candidate, reads=0, certificate_choices=[], pin_identities=[],
        batches=[], warnings=[], remember=True, accept_certificate=True,
        accept_pin=True, accept_token=True, token_row=0, certificate_row=None,
        error=False,
    )

    def discover(**options):
        state.reads += 1
        assert options["search_roots"] == ()
        assert options["extra_paths"] == (module,)
        if state.error:
            raise RuntimeError("tessera rimossa")
        return DiscoveryResult((state.candidate,), paths_checked=1, rejected=0)

    def certificate_exec(dialog):
        state.certificate_choices.append(dialog.selected_certificate())
        if state.certificate_row is not None:
            dialog.table.selectRow(state.certificate_row)
        dialog.remember_choice.setChecked(state.remember)
        return QDialog.DialogCode.Accepted if state.accept_certificate else QDialog.DialogCode.Rejected

    def pin_exec(dialog):
        state.pin_identities.append(dialog.certificate_label.text())
        dialog.pin_edit.setText("pin-test")
        if not state.accept_pin:
            dialog.reject()
        return QDialog.DialogCode.Accepted if state.accept_pin else QDialog.DialogCode.Rejected

    def token_exec(dialog):
        dialog.table.selectRow(state.token_row)
        return QDialog.DialogCode.Accepted if state.accept_token else QDialog.DialogCode.Rejected

    monkeypatch.setattr(CertificateSelectionDialog, "exec", certificate_exec)
    monkeypatch.setattr(PinDialog, "exec", pin_exec)
    monkeypatch.setattr(TokenSelectionDialog, "exec", token_exec)
    for method in ("warning", "information"):
        monkeypatch.setattr(QMessageBox, method, lambda *args: state.warnings.append(args[-1]))
    repository = ConfigRepository(workdir / "config.json")
    config = AppConfig()
    config.pkcs11.module_path = str(module)
    config.pkcs11.token_serial = "ff"
    config.pkcs11.certificate_label = "Certificato persona precedente"
    config.pkcs11.certificate_id = "ff"
    config.pkcs11.key_label = "Chiave persona precedente"
    repository.save(config)
    window = MFirmaQtWindow(
        repository, auto_scan=False,
        signing_discovery_controller=DiscoveryController(discoverer=discover),
    )
    qtbot.addWidget(window)
    source = workdir / "documento.pdf"
    source.write_bytes(b"PDF simulato")
    document = DocumentCandidate.from_path(source)
    window.preview_page.set_documents((document,), "Da scegliere")
    window.switchTo(window.preview_page)
    state.window = window
    state.real_start = window.start_batch

    def capture(provider, position_plan, **kwargs):
        state.batches.append((provider, position_plan, kwargs))
        return True

    monkeypatch.setattr(window, "start_batch", capture)

    def request():
        window.request_signing(SignaturePositionPlan(placements={}))
        qtbot.waitUntil(lambda: window._pending_signing is None, timeout=5000)
        assert window.preview_page.isEnabled()

    state.request = request
    yield state
    assert window.wait_for_workers()


def test_each_signature_reads_current_card_and_ignores_global_identity(signing_flow):
    state = signing_flow
    assert state.reads == 0
    state.request()
    first = state.batches[0][0].config
    assert first.token_serial == "41"
    assert first.certificate_id == "01"
    assert first.key_label == ""
    assert "Persona A" in state.pin_identities[0]
    second_certificate = replace(state.candidate.tokens[0].certificates[0], id_hex="02", subject="CN=Persona B")
    state.candidate = replace(state.candidate, tokens=(TokenCandidate(
        slot_id=1, label="Tessera", serial="B", serial_hex="42", certificates=(second_certificate,),
    ),))
    state.request()
    assert state.reads == 2
    second = state.batches[1][0].config
    assert second.token_serial == "42"
    assert second.certificate_id == "02"
    assert state.certificate_choices == [state.certificate_choices[0], second_certificate]
    assert "Persona B" in state.pin_identities[1]
    saved = state.window.repository.load().pkcs11
    assert saved.certificate_label == ""
    assert saved.token_serial == ""
    assert set(saved.remembered_certificates.values()) == {"01", "02"}
    assert state.window.settings_page.build_config().pkcs11.remembered_certificates == saved.remembered_certificates


def test_remembered_choice_is_preselected_but_still_confirmed(signing_flow):
    state = signing_flow
    token = state.candidate.tokens[0]
    second = replace(token.certificates[0], id_hex="02")
    state.candidate = replace(state.candidate, tokens=(replace(token, certificates=token.certificates + (second,)),))
    state.certificate_row = 1
    state.request()
    assert state.batches[-1][0].config.certificate_id == "02"
    state.certificate_row = None
    state.request()
    assert state.certificate_choices[-1] == second
    assert len(state.pin_identities) == 2
    state.remember = False
    state.request()
    assert state.window.repository.load().pkcs11.remembered_certificates == {}


def test_missing_remembered_certificate_requires_fresh_choice(signing_flow):
    state = signing_flow
    state.request()
    token = state.candidate.tokens[0]
    replacement = replace(token.certificates[0], id_hex="03")
    state.candidate = replace(state.candidate, tokens=(replace(token, certificates=(replacement,)),))
    state.request()
    assert state.certificate_choices[-1] == replacement
    assert state.batches[-1][0].config.certificate_id == "03"


@pytest.mark.parametrize("case", ["no_card", "no_certificates", "no_serial", "read_error", "cancel_certificate", "cancel_pin"])
def test_unavailable_or_cancelled_identity_never_starts_signing(signing_flow, case):
    state = signing_flow
    token = state.candidate.tokens[0]
    if case == "no_card":
        state.candidate = replace(state.candidate, tokens=())
    elif case == "no_certificates":
        state.candidate = replace(state.candidate, tokens=(replace(token, certificates=()),))
    elif case == "no_serial":
        state.candidate = replace(state.candidate, tokens=(replace(token, serial_hex=""),))
    elif case == "read_error":
        state.error = True
    elif case == "cancel_certificate":
        state.accept_certificate = False
    else:
        state.accept_pin = False
    state.request()
    assert not state.batches
    assert not state.window.repository.load().pkcs11.remembered_certificates
    if case != "cancel_pin":
        assert not state.pin_identities


@pytest.mark.parametrize("accept", [True, False])
def test_multiple_cards_require_current_token_selection(signing_flow, accept):
    state = signing_flow
    token = state.candidate.tokens[0]
    second = replace(token, slot_id=2, serial="B", serial_hex="42")
    state.candidate = replace(state.candidate, tokens=(token, second))
    state.token_row = 1
    state.accept_token = accept
    state.request()
    if accept:
        assert state.batches[-1][0].config.token_serial == "42"
    else:
        assert not state.batches
        assert not state.pin_identities


def test_selected_identity_is_used_by_batch_and_history(signing_flow, monkeypatch, qtbot):
    state = signing_flow

    class Provider:
        def __init__(self, config, signature):
            self.config = config

        def validate(self):
            pass

        @contextmanager
        def open(self, pin):
            assert pin == "pin-test"
            assert self.config.token_serial == "41"
            assert self.config.certificate_id == "01"
            yield self

        def sign_pdf(self, source, temporary, **kwargs):
            temporary.write_bytes(source.read_bytes() + b"SIGNED")

    monkeypatch.setattr("mfirma.ui.main_window.Pkcs11SigningProvider", Provider)
    monkeypatch.setattr(state.window, "start_batch", state.real_start)
    with qtbot.waitSignal(state.window.signing_controller.batchFinished, timeout=5000):
        state.request()
    job = state.window.result_page.model.jobs[0]
    assert job.status is JobStatus.SUCCEEDED
    assert job.destination.read_bytes().endswith(b"SIGNED")
    qtbot.waitUntil(lambda: bool(state.window.history_page.model.records), timeout=5000)
    assert state.window.history_page.model.records[0].certificate_label == "Firma · CN=Persona A"


def test_repeated_click_does_not_start_multiple_identity_requests(signing_flow, qtbot):
    state = signing_flow
    plan = SignaturePositionPlan(placements={})
    state.window.request_signing(plan)
    state.window.request_signing(plan)
    qtbot.waitUntil(lambda: state.window._pending_signing is None, timeout=5000)
    assert state.reads == 1
    assert len(state.batches) == 1


def test_leaving_preview_discards_pending_identity_request(signing_flow, qtbot):
    state = signing_flow
    state.window.request_signing(SignaturePositionPlan(placements={}))
    state.window.switchTo(state.window.queue_page)
    qtbot.waitUntil(lambda: state.window._pending_signing is None, timeout=5000)
    assert not state.certificate_choices
    assert not state.batches


def test_ambiguous_certificate_id_does_not_start_signing(signing_flow):
    state = signing_flow
    token = state.candidate.tokens[0]
    duplicate = replace(token.certificates[0], label="Altra firma")
    state.candidate = replace(state.candidate, tokens=(replace(token, certificates=token.certificates + (duplicate,)),))
    state.request()
    assert not state.batches
    assert not state.pin_identities
    assert any("stesso ID" in message for message in state.warnings)
