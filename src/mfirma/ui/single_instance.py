from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from ..config import default_config_path


PROTOCOL_VERSION = 1
MAX_FILES_PER_REQUEST = 100
MAX_MESSAGE_BYTES = 262_144


class RequestError(ValueError):
    pass


class ForwardStatus(StrEnum):
    DELIVERED = "delivered"
    NO_SERVER = "no_server"
    REJECTED = "rejected"


def instance_server_name(config_path: Path | None = None) -> str:
    """Return a stable name derived from the current user's config directory."""
    directory = (config_path or default_config_path()).expanduser().parent.resolve()
    digest = hashlib.sha256(str(directory).casefold().encode("utf-8")).hexdigest()[:16]
    return f"mfirma-{digest}-v1"


def startup_pdf_paths(arguments: list[str] | tuple[str, ...]) -> tuple[Path, ...]:
    paths: dict[str, Path] = {}
    for raw in arguments[1:]:
        if raw == "--qt-dashboard" or raw.startswith("-"):
            continue
        path = Path(raw).expanduser()
        if path.suffix.casefold() != ".pdf":
            continue
        absolute = path.resolve(strict=False)
        paths[str(absolute).casefold()] = absolute
    result = tuple(paths.values())
    if len(result) > MAX_FILES_PER_REQUEST:
        raise RequestError(
            f"Si possono aprire al massimo {MAX_FILES_PER_REQUEST} PDF per volta"
        )
    return result


def encode_file_request(paths: tuple[Path, ...]) -> bytes:
    if len(paths) > MAX_FILES_PER_REQUEST:
        raise RequestError(
            f"Si possono inoltrare al massimo {MAX_FILES_PER_REQUEST} PDF per volta"
        )
    values: list[str] = []
    for path in paths:
        if not path.is_absolute() or path.suffix.casefold() != ".pdf":
            raise RequestError("La richiesta contiene un percorso PDF non valido")
        value = str(path)
        if "\0" in value or len(value) > 32_767:
            raise RequestError("La richiesta contiene un percorso non valido")
        values.append(value)
    payload = json.dumps(
        {"version": PROTOCOL_VERSION, "files": values},
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    if len(payload) + 1 > MAX_MESSAGE_BYTES:
        raise RequestError("La richiesta di apertura è troppo grande")
    return payload + b"\n"


def decode_file_request(payload: bytes) -> tuple[Path, ...]:
    if not payload or len(payload) > MAX_MESSAGE_BYTES:
        raise RequestError("Dimensione richiesta non valida")
    try:
        raw = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RequestError("Richiesta non leggibile") from exc
    if not isinstance(raw, dict) or set(raw) != {"version", "files"}:
        raise RequestError("Formato richiesta non valido")
    if raw["version"] != PROTOCOL_VERSION:
        raise RequestError("Versione protocollo non supportata")
    files = raw["files"]
    if not isinstance(files, list) or len(files) > MAX_FILES_PER_REQUEST:
        raise RequestError("Numero di PDF non valido")
    unique: dict[str, Path] = {}
    for value in files:
        if not isinstance(value, str) or "\0" in value or len(value) > 32_767:
            raise RequestError("Percorso non valido")
        path = Path(value)
        if not path.is_absolute() or path.suffix.casefold() != ".pdf":
            raise RequestError("Sono accettati soltanto percorsi PDF assoluti")
        unique[str(path).casefold()] = path
    return tuple(unique.values())


def forward_file_request(
    server_name: str,
    paths: tuple[Path, ...],
    *,
    timeout_ms: int = 1500,
) -> ForwardStatus:
    message = encode_file_request(paths)
    socket = QLocalSocket()
    socket.connectToServer(server_name)
    if not socket.waitForConnected(timeout_ms):
        return ForwardStatus.NO_SERVER
    if socket.write(message) != len(message) or not socket.waitForBytesWritten(
        timeout_ms
    ):
        socket.abort()
        return ForwardStatus.REJECTED
    if not socket.waitForReadyRead(timeout_ms):
        socket.abort()
        return ForwardStatus.REJECTED
    response = bytes(socket.readAll()).strip()
    socket.disconnectFromServer()
    return (
        ForwardStatus.DELIVERED
        if response == b"OK"
        else ForwardStatus.REJECTED
    )


class SingleInstanceServer(QObject):
    filesReceived = Signal(object)
    requestRejected = Signal(str)

    def __init__(self, server_name: str, parent=None):
        super().__init__(parent)
        self.server_name = server_name
        self._server = QLocalServer(self)
        self._server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self._server.newConnection.connect(self._accept_connections)
        self._sockets: set[QLocalSocket] = set()

    def listen(self) -> bool:
        return self._server.listen(self.server_name)

    def remove_stale_and_listen(self) -> bool:
        QLocalServer.removeServer(self.server_name)
        return self.listen()

    def close(self) -> None:
        self._server.close()
        for socket in tuple(self._sockets):
            socket.blockSignals(True)
            socket.abort()
            socket.deleteLater()
        self._sockets.clear()

    @Slot()
    def _accept_connections(self) -> None:
        while self._server.hasPendingConnections():
            socket = self._server.nextPendingConnection()
            if socket is None:
                continue
            socket.setParent(self)
            self._sockets.add(socket)
            buffer = bytearray()

            def read_request(
                *, current_socket=socket, current_buffer=buffer
            ) -> None:
                current_buffer.extend(bytes(current_socket.readAll()))
                if len(current_buffer) > MAX_MESSAGE_BYTES:
                    self._reject(current_socket, "Richiesta troppo grande")
                    return
                if b"\n" not in current_buffer:
                    return
                payload, _separator, trailing = bytes(current_buffer).partition(b"\n")
                if trailing:
                    self._reject(current_socket, "Dati aggiuntivi non ammessi")
                    return
                try:
                    paths = decode_file_request(payload)
                except RequestError as exc:
                    self._reject(current_socket, str(exc))
                    return
                current_socket.write(b"OK\n")
                current_socket.disconnectFromServer()
                self.filesReceived.emit(paths)

            socket.readyRead.connect(read_request)
            socket.disconnected.connect(
                lambda current_socket=socket: self._forget_socket(current_socket)
            )
            if socket.bytesAvailable():
                read_request()

    def _reject(self, socket: QLocalSocket, message: str) -> None:
        self.requestRejected.emit(message)
        socket.write(b"ERROR\n")
        socket.disconnectFromServer()

    def _forget_socket(self, socket: QLocalSocket) -> None:
        self._sockets.discard(socket)
        socket.blockSignals(True)
        socket.deleteLater()
