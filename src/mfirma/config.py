from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class MonitorConfig:
    root: str = ""
    recursive_within_person: bool = True
    stability_seconds: int = 5


@dataclass(slots=True)
class OutputConfig:
    suffix: str = "_firmato"


@dataclass(slots=True)
class SignatureConfig:
    preset: str = "bottom_right"
    margin_points: float = 24.0
    width_points: float = 180.0
    height_points: float = 60.0
    reason: str = ""
    location: str = ""


@dataclass(slots=True)
class Pkcs11Config:
    module_path: str = ""
    token_label: str = ""
    certificate_label: str = ""
    key_label: str = ""


@dataclass(slots=True)
class AppConfig:
    config_version: int = 1
    monitor: MonitorConfig = field(default_factory=MonitorConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    signature: SignatureConfig = field(default_factory=SignatureConfig)
    pkcs11: Pkcs11Config = field(default_factory=Pkcs11Config)

    def validate(self) -> None:
        if self.config_version != 1:
            raise ValueError("Versione configurazione non supportata")
        if not 0 <= self.monitor.stability_seconds <= 3600:
            raise ValueError("La stabilità deve essere tra 0 e 3600 secondi")
        if self.signature.preset not in {
            "top_left",
            "top_right",
            "bottom_left",
            "bottom_right",
        }:
            raise ValueError("Preset firma non valido")
        if self.signature.margin_points < 0:
            raise ValueError("Il margine non può essere negativo")
        if self.signature.width_points <= 0 or self.signature.height_points <= 0:
            raise ValueError("Le dimensioni della firma devono essere positive")
        suffix = self.output.suffix
        if not suffix or any(char in suffix for char in '<>:"/\\|?*'):
            raise ValueError("Suffisso di output non valido")

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "AppConfig":
        allowed_top = {"config_version", "monitor", "output", "signature", "pkcs11"}
        unknown = set(raw) - allowed_top
        if unknown:
            raise ValueError(f"Campi configurazione sconosciuti: {', '.join(sorted(unknown))}")
        config = cls(
            config_version=int(raw.get("config_version", 1)),
            monitor=MonitorConfig(**raw.get("monitor", {})),
            output=OutputConfig(**raw.get("output", {})),
            signature=SignatureConfig(**raw.get("signature", {})),
            pkcs11=Pkcs11Config(**raw.get("pkcs11", {})),
        )
        config.validate()
        return config


def default_config_path() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return base / "mFirma" / "config.json"


class ConfigRepository:
    def __init__(self, path: Path | None = None):
        self.path = path or default_config_path()

    def load(self) -> AppConfig:
        if not self.path.exists():
            return AppConfig()
        with self.path.open("r", encoding="utf-8") as stream:
            raw = json.load(stream)
        if not isinstance(raw, dict):
            raise ValueError("La configurazione deve essere un oggetto JSON")
        return AppConfig.from_dict(raw)

    def save(self, config: AppConfig) -> None:
        config.validate()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary_name = tempfile.mkstemp(
            prefix="config-", suffix=".tmp", dir=self.path.parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
                json.dump(asdict(config), stream, ensure_ascii=False, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)

