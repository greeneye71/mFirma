from __future__ import annotations

import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication

from mfirma.ui.single_instance import (
    MAX_FILES_PER_REQUEST,
    ForwardStatus,
    RequestError,
    SingleInstanceServer,
    decode_file_request,
    encode_file_request,
    forward_file_request,
    instance_server_name,
    startup_pdf_paths,
)


def test_protocol_accepts_100_unicode_pdfs(workdir):
    paths = tuple(
        (workdir / f"pratica à {index:03}.pdf").resolve()
        for index in range(MAX_FILES_PER_REQUEST)
    )

    decoded = decode_file_request(encode_file_request(paths))

    assert decoded == paths


def test_protocol_deduplicates_paths(workdir):
    path = (workdir / "documento.pdf").resolve()

    decoded = decode_file_request(encode_file_request((path, path)))

    assert decoded == (path,)


def test_protocol_rejects_too_many_files_and_arbitrary_commands(workdir):
    paths = tuple(
        (workdir / f"{index}.pdf").resolve()
        for index in range(MAX_FILES_PER_REQUEST + 1)
    )
    with pytest.raises(RequestError, match="massimo"):
        encode_file_request(paths)
    with pytest.raises(RequestError, match="Formato"):
        decode_file_request(b'{"version":1,"files":[],"command":"sign"}')
    with pytest.raises(RequestError, match="assoluti"):
        decode_file_request(b'{"version":1,"files":["relativo.pdf"]}')


def test_startup_paths_keep_only_unique_pdf_arguments(workdir):
    first = workdir / "uno.pdf"
    second = workdir / "due.PDF"

    paths = startup_pdf_paths(
        ["mfirma", "--qt-dashboard", str(first), "note.txt", str(second), str(first)]
    )

    assert paths == (first.resolve(), second.resolve())


def test_startup_paths_reject_more_than_100_unique_pdfs(workdir):
    arguments = ["mfirma"] + [
        str(workdir / f"{index}.pdf")
        for index in range(MAX_FILES_PER_REQUEST + 1)
    ]

    with pytest.raises(RequestError, match="massimo"):
        startup_pdf_paths(arguments)


def test_local_server_is_user_only_and_forwards_request(qtbot, workdir):
    name = f"mfirma-test-{uuid.uuid4().hex}"
    application = QApplication.instance()
    server = SingleInstanceServer(name, application)
    path = (workdir / "documento con spazi.pdf").resolve()
    client = QLocalSocket(application)
    try:
        assert server.listen(), server._server.errorString()
        assert (
            server._server.socketOptions()
            == QLocalServer.SocketOption.UserAccessOption
        )
        with qtbot.waitSignal(server.filesReceived, timeout=3000) as signal:
            client.connectToServer(name)
            assert client.waitForConnected(1000)
            client.write(encode_file_request((path,)))
            client.flush()

        assert signal.args == [(path,)]
        qtbot.waitUntil(lambda: client.bytesAvailable() > 0, timeout=1000)
        assert bytes(client.readAll()).strip() == b"OK"
    finally:
        client.blockSignals(True)
        client.abort()
        server.close()


def test_empty_request_activates_existing_instance(qtbot):
    name = f"mfirma-test-{uuid.uuid4().hex}"
    application = QApplication.instance()
    server = SingleInstanceServer(name, application)
    client = QLocalSocket(application)
    try:
        assert server.listen(), server._server.errorString()
        with qtbot.waitSignal(server.filesReceived, timeout=3000) as signal:
            client.connectToServer(name)
            assert client.waitForConnected(1000)
            client.write(encode_file_request(()))
            client.flush()

        assert signal.args == [()]
    finally:
        client.blockSignals(True)
        client.abort()
        server.close()


def test_server_name_is_stable_for_config_directory(workdir):
    first = instance_server_name(workdir / "config-a.json")
    second = instance_server_name(workdir / "config-b.json")

    assert first == second
    assert first.startswith("mfirma-")


def test_forward_reports_missing_server(workdir):
    path = (workdir / "documento.pdf").resolve()

    status = forward_file_request(
        f"mfirma-missing-{uuid.uuid4().hex}", (path,), timeout_ms=20
    )

    assert status is ForwardStatus.NO_SERVER


def test_real_launcher_process_forwards_to_running_server(qtbot, workdir):
    name = f"mfirma-test-{uuid.uuid4().hex}"
    application = QApplication.instance()
    server = SingleInstanceServer(name, application)
    path = (workdir / "documento à.pdf").resolve()
    script = (
        "import sys; from pathlib import Path; "
        "from mfirma.ui.single_instance import forward_file_request; "
        "print(forward_file_request(sys.argv[1], (Path(sys.argv[2]),)))"
    )
    process = None
    try:
        assert server.listen(), server._server.errorString()
        with qtbot.waitSignal(server.filesReceived, timeout=5000) as signal:
            process = subprocess.Popen(
                [sys.executable, "-c", script, name, str(path)],
                cwd=Path(__file__).parents[1],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            )
        stdout, stderr = process.communicate(timeout=3)

        assert signal.args == [(path,)]
        assert process.returncode == 0, stderr
        assert stdout.strip() == ForwardStatus.DELIVERED
    finally:
        if process is not None and process.poll() is None:
            process.kill()
        server.close()
