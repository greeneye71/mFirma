from __future__ import annotations

from pathlib import Path

from mfirma.launcher import launch_or_forward
from mfirma.ui.single_instance import ForwardStatus, RequestError


def test_launcher_exits_without_spawning_when_request_is_forwarded(monkeypatch):
    spawned = []
    monkeypatch.setattr(
        "mfirma.launcher.forward_file_request",
        lambda _name, _paths: ForwardStatus.DELIVERED,
    )
    monkeypatch.setattr("mfirma.launcher.subprocess.Popen", spawned.append)

    assert launch_or_forward(["launcher", r"C:\Pratiche\uno.pdf"]) == 0
    assert spawned == []


def test_launcher_starts_main_application_when_no_instance_exists(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "mfirma.launcher.forward_file_request",
        lambda _name, _paths: ForwardStatus.NO_SERVER,
    )
    monkeypatch.setattr("mfirma.launcher.sys.executable", r"C:\Python\pythonw.exe")
    monkeypatch.setattr(
        "mfirma.launcher.subprocess.Popen",
        lambda command, **options: calls.append((command, options)),
    )

    assert launch_or_forward(["launcher", r"C:\Pratiche\uno.pdf"]) == 0
    assert calls == [
        (
            [
                r"C:\Python\pythonw.exe",
                "-m",
                "mfirma",
                r"C:\Pratiche\uno.pdf",
            ],
            {"close_fds": True},
        )
    ]


def test_launcher_delegates_invalid_arguments_to_main_application(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "mfirma.launcher.startup_pdf_paths",
        lambda _arguments: (_ for _ in ()).throw(RequestError("troppi PDF")),
    )
    monkeypatch.setattr("mfirma.launcher.sys.executable", r"C:\Python\pythonw.exe")
    monkeypatch.setattr(
        "mfirma.launcher.subprocess.Popen",
        lambda command, **options: calls.append((command, options)),
    )

    assert launch_or_forward(["launcher", "uno.pdf"]) == 0
    assert calls[0][0] == [
        r"C:\Python\pythonw.exe",
        "-m",
        "mfirma",
        "uno.pdf",
    ]


def test_windows_launcher_forwards_all_received_arguments():
    root = Path(__file__).parents[1]
    launcher = (root / "avvia_mFirma.cmd").read_text(encoding="utf-8")
    registration = (root / "scripts" / "registra_menu_esplora.ps1").read_text(
        encoding="utf-8"
    )

    assert "-m mfirma.launcher %*" in launcher
    assert "MultiSelectModel' -Value 'Player'" in registration
    assert '"%1"' in registration
