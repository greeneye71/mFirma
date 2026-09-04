from dataclasses import asdict
from pathlib import Path

from mfirma.config import AppConfig, ConfigRepository


def test_config_roundtrip_has_no_pin_field(workdir: Path):
    path = workdir / "config.json"
    config = AppConfig()
    config.monitor.root = r"\\server\Da firmare"
    config.pkcs11.module_path = r"C:\Vendor\token.dll"
    config.pkcs11.certificate_label = "Firma"

    repository = ConfigRepository(path)
    repository.save(config)
    loaded = repository.load()

    assert asdict(loaded) == asdict(config)
    assert "pin" not in path.read_text(encoding="utf-8").casefold()
