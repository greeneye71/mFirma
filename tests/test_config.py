from dataclasses import asdict
from pathlib import Path

from mfirma.config import AppConfig, ConfigRepository


def test_config_roundtrip_has_no_pin_field(workdir: Path):
    path = workdir / "config.json"
    config = AppConfig()
    config.monitor.root = r"\\server\Da firmare"
    config.pkcs11.module_path = r"C:\Vendor\token.dll"
    config.pkcs11.certificate_label = "Firma"
    config.pkcs11.certificate_id = "445333"

    repository = ConfigRepository(path)
    repository.save(config)
    loaded = repository.load()

    assert asdict(loaded) == asdict(config)
    assert "pin" not in path.read_text(encoding="utf-8").casefold()


def test_old_config_without_certificate_id_remains_supported():
    config = AppConfig.from_dict(
        {
            "config_version": 1,
            "pkcs11": {
                "module_path": r"C:\Vendor\token.dll",
                "certificate_label": "Firma",
            },
        }
    )

    assert config.pkcs11.certificate_id == ""
    assert config.signature.appearance_variant == "complete"
    assert config.signature.width_points == 240.0
    assert config.signature.height_points == 92.0


def test_old_default_appearance_dimensions_are_migrated():
    config = AppConfig.from_dict(
        {
            "config_version": 1,
            "signature": {
                "preset": "bottom_right",
                "margin_points": 24.0,
                "width_points": 180.0,
                "height_points": 60.0,
                "reason": "",
                "location": "",
            },
        }
    )

    assert config.signature.appearance_variant == "complete"
    assert config.signature.width_points == 240.0
    assert config.signature.height_points == 92.0
