from types import SimpleNamespace

from qfluentwidgets import FluentIcon

from mfirma.ui.application import configure_application, configure_windows_identity


def test_application_uses_tray_certificate_icon(qapp):
    previous = qapp.windowIcon()
    try:
        configure_application(qapp)
        actual = qapp.windowIcon().pixmap(32, 32).toImage()
        expected = FluentIcon.CERTIFICATE.icon().pixmap(32, 32).toImage()
        assert not actual.isNull()
        assert actual == expected
    finally:
        qapp.setWindowIcon(previous)


def test_windows_identity_is_dedicated_to_mfirma(monkeypatch):
    calls = []
    def set_app_id(value):
        calls.append(value)
        return 0
    monkeypatch.setattr("mfirma.ui.application.sys.platform", "win32")
    monkeypatch.setattr("ctypes.windll", SimpleNamespace(shell32=SimpleNamespace(
        SetCurrentProcessExplicitAppUserModelID=set_app_id,
    )), raising=False)
    configure_windows_identity()
    assert calls == ["mFirma.Desktop"]


def test_windows_identity_failure_does_not_block_startup(monkeypatch):
    def fail(value):
        raise OSError("not available")
    monkeypatch.setattr("mfirma.ui.application.sys.platform", "win32")
    monkeypatch.setattr("ctypes.windll", SimpleNamespace(shell32=SimpleNamespace(
        SetCurrentProcessExplicitAppUserModelID=fail,
    )), raising=False)
    configure_windows_identity()
